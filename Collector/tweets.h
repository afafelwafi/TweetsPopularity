#include <string>
#include <iostream>
#include <sstream>


namespace tweetoscope {

  using timestamp = std::size_t;
  namespace source {
    using idf = std::size_t;
  }
  namespace cascade {
    using idf = std::size_t;
  }

  struct tweet {
    std::string type = "";
    std::string msg  = "";
    cascade::idf  cascade=0;
    timestamp time   = 0;
    double magnitude = 0;
    source::idf source = 0;
    std::string info = "";
  };

  inline std::string get_string_val(std::istream& is) {
    char c;
    is >> c; // eats  "
    std::string value;
    std::getline(is, value, '"'); // eats tweet", but value has tweet
    return value;
  }

  inline std::istream& operator>>(std::istream& is, tweet& t) {
    // A tweet is  : {"type" : "tweet"|"retweet",
    //                "msg": "...",
    //                "time": timestamp,
    //                "magnitude": 1085.0,
    //                "source": 0,
    //                "info": "blabla"}
    std::string delimiter("cascade=");
    std::string buf;
    char c;
    is >> c; // eats '{'
    is >> c; // eats '"'
    while(c != '}') {
      std::string tag;
      std::getline(is, tag, '"'); // Eats until next ", that is eaten but not stored into tag.
      is >> c;  // eats ":"
      if     (tag == "type")    t.type = get_string_val(is);
      else if(tag == "msg")     t.msg  = get_string_val(is);
      else if(tag == "info")   { t.info = get_string_val(is);

      std::size_t pos = t.info.find("=");      // position of "live" in str

      std::string str3 = t.info.substr(pos+1);
      std::stringstream geek(str3);

    // The object has the value 12345 and stream
    // it to the integer x
      int x = 0;
      geek >> x;
	t.cascade=x;
      }
      else if(tag == "t")       is >> t.time;
      else if(tag == "m")       is >> t.magnitude;
      else if(tag == "source")  is >> t.source;
      else if(tag == "cascade")  is >> t.cascade;

      is >> c; // eats either } or ,
      if(c == ',')
        is >> c; // eats '"'
    }
    return is;
  }
}

