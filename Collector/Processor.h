#include "cascade.h"
#include "tweetoscopeCollectorParams.h"
#include <iostream>
#include <sstream>
#include <map>
#include <vector>
#include <tuple>
#include <string>
#include <stdexcept>
#include <string>
#include <sstream>
#include <cppkafka/cppkafka.h>



struct Processor {

  using source=tweetoscope::source::idf;
  using timestamp=tweetoscope::timestamp;
  using idf=tweetoscope::cascade::idf;
  using ref = std::shared_ptr<Cascade>;


  source  src;                  /// source of a processor
  priority_queue cas_queue;                 ///cascades queue
  std::string name="Processor_";
  timestamp time; ///  last modification time
  std::map<timestamp, std::queue<std::weak_ptr<Cascade>>> fifo;
  std::map<idf,std::weak_ptr<Cascade>>cascades;
  std::vector<std::size_t> observations;
  std::size_t  terminated;
  std::size_t min_cascade_size;


  ///create a processor from a source
  Processor(const source& sc,const timestamp& tm) : src(sc),time(tm){
   ///ADDD THE WEAK PTR IN FIFOS
     //fif.push(ref_cascade);
    terminated=0;
    min_cascade_size=0;
    name+=std::to_string(sc);
    }
  // Processor() :Processor(1.0) {}
};




std::ostream& operator<<(std::ostream& os, const Processor& m) {
  os << "{\"source\": \"" << m.src << "\", \"name\": " << m.name << "\", \"time\": " << m.time;
  if(!m.cascades.empty()) {/// Dans les cascedes
  os << ", \"cascades\": [";
    for (auto val= m.cascades.begin();val!=m.cascades.end();++val){
        auto cascade=val->second;
/*         if (auto observe = cascade.lock()){
            std::cout<<"[";
            std::cout << *observe<< std::endl;//MOntrer les cascades
            }
        std::cout<<"],"; */


  }
  os << "]}"<<std::endl;
  }
  else{
    os << "\", \"cascades\": []}"<<std::endl;

  }
    return os;
}


struct Program {
  using idf=tweetoscope::cascade::idf;
  using timestamp=tweetoscope::timestamp;
  using source=tweetoscope::source::idf;
  using ref  = std::shared_ptr<Cascade>;
  //static  cppkafka::Configuration config_pro = {{ "bootstrap.servers", "localhost:9092"}};



  std::map<source, Processor> program;/// allouer à chaque processeur une source


  ////////////add a processor if it doesn't exist according to a surce and add times

  void operator+=(const std::tuple<source,std::vector<std::size_t>,std::size_t,std::size_t>& data) { // arg = {module_name, teacher, coefficient
     
      auto [it, is_newly_created] = program.try_emplace(std::get<0>(data),std::get<0>(data),0);

    if(is_newly_created){ ///just created{
            auto proces=it->second;
            proces.observations=std::get<1>(data);
            proces.terminated=std::get<2>(data);
            proces.min_cascade_size=std::get<3>(data);
            std::queue<std::weak_ptr<Cascade>> fif;
            for(auto time: proces.observations ){
                auto it=proces.fifo.try_emplace(time,fif);
                    }

/*       std::cout <<"----------------------------------"<< std::endl;
      std::cout << "Processor " << it->second << " created with source \"" << it->first << std::endl;
      std::cout<<"process_terminated : "<<proces.terminated<<std::endl;

      std::cout <<"----------------------------------"<< std::endl; */
    program.at(std::get<0>(data))=proces;
}
    else{
    auto proces=it->second;
    proces.observations=std::get<1>(data);
    proces.terminated=std::get<2>(data);
    proces.min_cascade_size=std::get<3>(data);
    proces.observations=std::get<1>(data);
    program.at(std::get<0>(data))=proces;



    }


    }



    //else { ////already found let's update it
      //it->second.time   = std::get<1>(data); /// the only thing to update is source timin

////////////add a processor if it doesn't exist according to a source and a cascade shared pointeer  config

  
  void operator+=(const std::tuple<source,timestamp,idf,tweetoscope::tweet,std::string,std::string,cppkafka::Producer&>& data) {
      //std::cout <<"-----------------Hi-----------------"<<std::endl;
    cppkafka::MessageBuilder builder_p(std::get<4>(data));
    cppkafka::MessageBuilder builder_c(std::get<5>(data));
    auto process=program.at(std::get<0>(data));///GET THE PROCESS WORKING ON THE CURRENT SOURCE
    //std::cout<<"-------cascade number :"<<std::get<3>(data).cascade<<"--------------------"<<std::endl;
    auto it =process.cascades.find(std::get<2>(data));///LET'S CHECK IF THE PROCESS HAS ALREADY A CASCADE WITH IDF
    //std::cout<<"Found Cascade"<<std::endl;
    if (it==process.cascades.end()){ ///NO CASCADE WITH THIS IDF TWO POSSIBILITIES EITHER DELETED EITHER NEVER CREATED SO LET'S CREATE ONE IF WE HAVE A NEW TWEET
    if (std::get<3>(data).type=="tweet"){
     //std::cout<<"-------------------its a tweet---------------"<<std::endl;
     Cascade new_cascade(std::get<2>(data));///CREATE A CASCADE



     new_cascade=std::get<3>(data);///WE WILL ADD A TWEET TO CASCADE
     //std::cout<<new_cascade<<std::endl;

     auto ref_casca = std::make_shared<Cascade>(new_cascade);/// SHARED POINTER OF CASCAD
      process.cascades[std::get<2>(data)]=ref_casca;  /// WE WILL EMPLACE THE PONTER IN CASCADES



    ///ADD A SHARED POINTER IN THE QUEUE
       //ref_cascade->location =
        ref_casca->location = process.cas_queue.push(ref_casca);
        //process.cas_queue.increase(ref_cascade->location, ref_cascade);

     ///ADDD THE WEAK PTR IN FIFOS

     //fif.push(ref_cascade);
     for(auto time: process.observations ){

        process.fifo.at(time).push(ref_casca);
        //std::cout<<process.fifo.at(time).size()<<std::endl;

        }

     program.at(std::get<0>(data))=process;

     }
    program.at(std::get<0>(data))=process;



     }








     else{//DASCADE EXISTS SO IT'S ALREAD IN THE QUEUE

     //std::cout<<"------------------------its a retweet------------------"<<std::endl;
         ///CASCADE ALREADY EXISTS it is a weak pointer in the cascade
           // std::cout<<"-------------RETWEET------------"<<std::endl;


            ///TIME CHECK !!!!

            auto ref_cascade=it->second.lock(); //SHARED POINTER OF THE CASCADE

                                 //std::cout<<"------------------------its a retweet------------------"<<std::endl;
                                //std::cout<<*ref_cascade<<std::endl;


            auto prev_time=ref_cascade->getime(); //PREV TIME OF THE CASCADE

            auto prev_time_init=ref_cascade->getcascade().front().first;

            auto next_time=std::get<3>(data).time;/// NEXT TIME IF WE CHANGE IT

      //std::cout<<next_time-prev_time<<std::endl;

        ///ADDD THE WEAK PTR IN FIFOS
             for(auto time: process.observations ){///FOR EACH FIFO
                    //std::cout<<"                 time:"<<time<<"             "<<std::endl;

                auto current_queue=process.fifo.at(time);/// WE GET THE CASCADE FIFO AT TIME OF OBSERVATION T
                //std::cout<<current_queue.size()<<std::endl;
                while (!current_queue.empty()){ //F THE CURRENT QUEUE IS
                        auto current_cas=current_queue.front(); ///FOR EACH PARTIAL CASCADE ###WE CHECK THE FIRST CASCADE
                        auto ob =current_cas.lock();

                        //std::cout<<*ob<<std::endl;
                        if (next_time-prev_time_init>=time){ ///WE CHECH TIME CONSTRAINT

                            process.fifo.at(time).pop();///we delete it from fifo
                            if ((current_cas.lock())->getsize()>process.min_cascade_size){/// CHECK SIZE CONSTRIANT
                                    std::ostringstream ostr;
                                    sendSerie(ostr,*(current_cas.lock()),time);
                                    std::string message {ostr.str()};
                                    builder_c.payload(message);
				    (std::get<6>(data)).produce(builder_c);
                                    //std::cout<<"sent partitions"<<std::endl;

                            }

                        }
                        current_queue.pop();
                    }
                    }



                       
                         *ref_cascade=std::get<3>(data);

             program.at(std::get<0>(data))=process;


                  if(!process.cas_queue.empty()){

                    if(next_time-prev_time>process.terminated){

                            //std::cout<<"here we are"<<std::endl;
                            auto to_send=process.cas_queue.top();
                            //process.cas_queue.pop();
                            process.cascades.erase(std::get<2>(data));
                            program.at(std::get<0>(data))=process;

                            if (to_send->getsize()>process.min_cascade_size){///SEND IT
                                std::ostringstream ostr;
                                sendPropertie(ostr,*(ref_cascade));
                                std::string message {ostr.str()};
                                for(auto time: process.observations ){
                                std::string str_time=std::to_string(time);
                                builder_p.key(str_time).payload(message);
                                (std::get<6>(data)).produce(builder_p);}
                  

                                //std::cout<<"sent cascade"<<std::endl;

                    }
                    }


                }
                                        showpq(process.cas_queue);





     /*   std::cout << "Program after the retweet: size " <<process.cas_queue.size()<< std::endl;

        std::cout <<"----------------------------------"<< std::endl;

         std::cout << "Program after the retweet: cascades organization " << std::endl;
         showpq(process.cas_queue);*/










   // process.cascades.at(std::get<2>(data))=it->second;





    //program.at(std::get<0>(data))=process;



    //program.at(std::get<0>(data)).cascades=process.cascades;
    //program.at(std::get<0>(data)).fifo=process.fifo;
    //program.at(std::get<0>(data)).cas_queue=process.cas_queue;



            program.at(std::get<0>(data))=process;

}
             //program.at(std::get<0>(data)).fifo=process.fifo;
             //program.at(std::get<0>(data)).cas_queue=process.cas_queue;
             //program.at(std::get<0>(data)).cascades=process.cascades;

             program.at(std::get<0>(data))=process;

            //std::cout <<"----------------------------------"<< std::endl;

}




  /*void operator+=(const std::tuple<source,idf,tweetoscope::tweet>& data) { // arg = {module_name, teacher, coefficient addd tweee
    auto process=program.at(std::get<0>(data));//GOT THE PROCESS
    std::cout<<"Found"<<std::endl;
    std::cout<<process.cascades.size()<<std::endl;

    auto cascade= process.cascades.at(std::get<1>(data));//FOUND THE CASCADE

    auto observe=cascade.lock();
    std::cout<< *observe<<std::endl;


          }



    //ncrease, queue.decrease and queue.update methods can be
      ref change_pro(std::get<2>(data));
      *change_pro =process.cas_queue.size()-1;
      process.cas_queue.increase(change_pro->location, change_pro);
    std::cout << "Program after retweet: " << std::endl;
    std::cout << "Processor " << process;

    //else { ////already found let's update it
      //it->second.time   = std::get<1>(data); /// the only thing to update is source timin
      */













  // This removes a process
void operator-=(const source& src) {
    if(auto it = program.find(src); it != program.end())
      program.erase(it);
  }

};

std::ostream& operator<<(std::ostream& os, const Program& prc) {
  os << "Program : " << std::endl;
  for(auto& name_processor: prc.program)//nam_processor : pair(source,processor)
    os << "  " << name_processor.first << " : " <<name_processor.second << std::endl;
  return os;
}


