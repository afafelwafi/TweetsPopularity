#include "tweets.h"
#include <memory>
#include <boost/heap/binomial_heap.hpp>
#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include <sstream>
// Cascade  is what we store in the queue. Let us first define pointers
// to it, and a queue type that handles such pointers.

class Cascade; // Now, we can talk about the class as long as we do
           // not need to knwow what it is made of.

using cascade_ref  = std::shared_ptr<Cascade>;

// This is the comparison functor for boost queues.
struct cascade_ref_comparator {
  bool operator()(cascade_ref op1, cascade_ref op2) const; // Defined later.
};

// We define our queue type.
using priority_queue = boost::heap::binomial_heap<cascade_ref,
                          boost::heap::compare<cascade_ref_comparator>>;
using idf=tweetoscope::cascade::idf;
// This is the actual class definition.
class Cascade {
using timestamp=unsigned int;
private:
  int cas_size;
  timestamp  time;// Timestamp of cascade last time
  timestamp Tobs;
  idf value;///identifier of cascade
  std::vector<std::pair<timestamp, double>> tweets;///retweeets

public:
  priority_queue::handle_type location; // This is "where" the element
                    // is in the queue. This is
                    // needed when we change the
                    // priority.

  Cascade(idf value): value(value), cas_size(0) ,Tobs(0){}
  timestamp getime(){return time;}
  void setTobs(timestamp t){Tobs=t;}
  int getsize(){return cas_size;}
  idf getvalue(){return value;}
  std::vector<std::pair<timestamp, double>> getcascade(){return tweets;}
  bool operator<(const Cascade& other) const {return time < other.time;}

  void operator=(tweetoscope::tweet retweet)
  {time = retweet.time;
  tweets.emplace_back(retweet.time,retweet.magnitude);
  cas_size=cas_size+1;
  }
    friend  std::ostream& sendSerie(std::ostream& os,const Cascade& e,timestamp tobs);
   friend  std::ostream&  sendPropertie(std::ostream& os, const Cascade& e);


  friend std::ostream& operator<<(std::ostream& os, const Cascade& e);
};
using timestamp=unsigned int;
std::ostream& sendSerie(std::ostream& os,const Cascade& e,timestamp tobs){
    os<<"{ \"type\": \'serie\', \"cid\": "<<std::to_string(e.value)<<", \"msg\": \'None\', \"T_obs\": "<<std::to_string(tobs)<<", \"tweets\": "<<"[";
    int i=0;
    for(auto twt:e.tweets){
        if (i<e.tweets.size()-1){ os<<"("<<std::to_string(twt.first)<<","<<std::to_string(twt.second)<<"),";}
        else {os<<"("<<std::to_string(twt.first)<<","<<std::to_string(twt.second)<<")]";}
        i++;
      }
    os<<"}";
    return os;
}

std::ostream&  sendPropertie(std::ostream& os, const Cascade& e){
    os<<"{ \"type\": \"size\", \"cid\": "<<e.value<<", \"n_tot\": "<<e.cas_size<<", \"t_end\": "<<e.time<<" }";
    return os ;

}



std::ostream& operator<<(std::ostream& os, const Cascade& e) {
  os <<"{\"cascade_id\":"<< e.value<<","<<"\"tweets\":"<<"{";
  int i=0;
  for(auto twt:e.tweets){
    if (i<e.tweets.size()-1){ os<<"{\"time\":" << std::to_string(twt.first) <<",\"magnitude\":" << std::to_string(twt.second) << "},";}
    else {os<<"{\"time\":" << twt.first <<",\"magnitude\":" << twt.second << "}}";}
    i++;
  }

  return os;
}

// Now, we know how Element is made, we can write the comparison
// functor from < implemented in Element.
bool cascade_ref_comparator::operator()(cascade_ref op1, cascade_ref op2) const {
  return *op1 < *op2;
}

// This is a convenient function for pointer allocation.
cascade_ref cascade(int value, const double& msg,int tm) {return std::make_shared<Cascade>(value);}

void showpq(priority_queue  gq)
{
    priority_queue  g = gq;
    while(!g.empty()) {
    auto ref = g.top();
    g.pop();
    //std::cout << ref->getvalue() << std::endl;
  }
};

/*
int main(int argc, char* argv[]) {
  priority_queue queue;

  std::vector<std::string> names = {std::string("zero"), "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"};

  int v = 0;
  element_ref two;
  for(const auto& name : names) {
    auto ref = element(v++, name);
    if(v == 3) two = ref;
    ref->location = queue.push(ref);



  }

  // Now, we change the priority of two. We increase it, but
  // queue.increase, queue.decrease and queue.update methods can be
  // used.
  *two = 5;
  queue.increase(two->location, two);

  // Let us flush and print the queue, from highest to lowest
  // priority.
  while(!queue.empty()) {
    auto ref = queue.top();
    queue.pop();
    std::cout << *ref << std::endl;
  }

  return 0;
}
*/
