#include <iostream>
#include <ostream>
#include <sstream>
#include <map>
#include <vector>
#include <tuple>
#include <stdexcept>
#include <string>
#include <memory>
#include "Processor.h"


int main(int argc, char* argv[]) {
   Program program;

	// Read messages

  if(argc != 2) {
    std::cout << "Usage : " << argv[0] << " params.config" << std::endl;
    return 0;
  }
  tweetoscope::params::collector params(argv[1]);
   // Create the config
	cppkafka::Configuration config = {
		{ "bootstrap.servers", params.kafka.brokers},
		{ "auto.offset.reset", "earliest" },
		{ "group.id", "myOwnPrivateGroup" }
	};
	cppkafka::Configuration configp = {
		{ "bootstrap.servers", params.kafka.brokers},
        
	};


	// Create the consumer
	cppkafka::Consumer consumer(config);
	cppkafka::Producer producer(configp);
	consumer.subscribe({params.topic.in});
	cppkafka::MessageBuilder builder(params.topic.out_series);




  	// Read messages
  	std::cout<< "Configuration is done" <<std::endl;
	while(true) {
	  auto msg = consumer.poll();
	  if( msg && ! msg.get_error() ) {
	    tweetoscope::tweet twt;

	    auto key = tweetoscope::cascade::idf(std::stoi(msg.get_key()));
	    auto istr = std::istringstream(std::string(msg.get_payload()));
	    istr >> twt;
	    //std::cout << istr.str() << std::endl;
	    // we read msg it's cool let's decide what to do with
	    auto t_source= twt.source; //we have the source here
	    auto t_cascade=twt.cascade;
	    auto t_time=twt.time;
	    auto t_type=twt.type;
	    auto t_msg=twt.msg;
        auto t_magnitude=twt.magnitude;

        program+={t_source,params.times.observation,params.times.terminated,params.cascade.min_cascade_size};

    /////////////////
     // add a processor with the corrensponding source

    //std::cout<<  source<< std::endl;
    //std::cout<< cascade<< std::endl;
    //if (t_type=="tweet"){
    //std::cout<<program<<std::endl;
        program+={t_source,t_time,twt.cascade,twt,params.topic.out_properties, params.topic.out_series,producer};
        }

        //std::cout<<program<<std::endl;
            //std::cout<<program<<std::endl;}

          //std::cout<<program[t_source].cascades.size()<<std::endl;}
     //}
    //    if (t_type=="retweet")

       // program+={t_source,twt.cascade,twt}

	    //get in the process of this source


	  }
	  return 0;

}

