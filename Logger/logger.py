import argparse, os, atexit
import logging
import json
import time
import textwrap
from termcolor import colored

from kafka import KafkaProducer, KafkaConsumer

default_broker_list = "localhost:9091,localhost:9092"
default_log_topic = "logs"

class KafkaHandler(logging.Handler):
    """Class to instantiate the kafka logging facility."""

    def __init__(self, hostlist, topic='logs', tls=None):
        """Initialize an instance of the kafka handler."""
        logging.Handler.__init__(self)
        self.producer = KafkaProducer(bootstrap_servers=hostlist,
                                      value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                                      linger_ms=10)
        self.topic = topic
        self.record = None
        
        
    def emit(self, record):
        """Emit the provided record to the kafka_client producer."""
        # drop kafka logging to avoid infinite recursion
        if 'kafka.' in record.name:
            return

        try:
            # apply the logger formatter
            msg = self.format(record)

            self.producer.send(self.topic, {
                't': int(time.time()),
                'source': record.name,
                'level': record.levelname,
                'message': msg})
            self.flush(timeout=1.0)
        except Exception:
            logging.Handler.handleError(self, record)

    def flush(self, timeout=None):
        """Flush the objects."""
        self.producer.flush(timeout=timeout)

    def close(self):
        """Close the producer and clean up."""
        self.acquire()
        try:
            if self.producer:
                self.producer.close()

            logging.Handler.close(self)
        finally:
            self.release()
         
def get_logger(name, debug=False, topic=default_log_topic, broker_list=default_broker_list, levels=[]):
    logger = logging.getLogger(name)
    if debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logger.setLevel(level)
   
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('{} - %(levelname)-8s | %(message)s'.format(name))
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    ch = KafkaHandler(broker_list, topic = topic)
    ch.setLevel(level)
    formatter = logging.Formatter('%(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    logger.info("Logging on.")    
    atexit.register(lambda: logger.info("Logging off."))
    return logger



class Logger:
    default_columns = [
        { "field": "t",       "length": 5,    "align": ">", "name": "time" },
        { "field": "source",  "length": 9,   "align": "^", "name": "source" },
        { "field": "level",   "length": 8,    "align": "^", "name": "level" },
        { "field": "message", "length": None, "align": "<", "name": "message" },
    ]
    
    def __init__(self, columns=default_columns, log_sep=None, skip_line=True, levels={}, sources={}):
            
        self.columns = columns
        self.elastic_columns = {}
        self.preprocessors = {}
        self.postprocessors = {}
        self.sep = "|"
        self.header_sep = "="
        self.log_sep = log_sep
        self.skip_line = skip_line
        self.levels = { l.upper() for l in levels }
        self.sources = { s for s in sources }
        
        for col in columns:
            if col['length'] is None:
                self.elastic_columns[col['field']] = col

        self.headers = { col["field"]: col["name"] for col in self.columns }
        self.print(self.headers, log_sep = self.header_sep)

    def get_terminal_width(self):
        return os.get_terminal_size()[0]
    
    def draw_line(self, c):
        print(c * self.get_terminal_width())

    def add_preprocessor(self, field, f):
        self.preprocessors[field] = f
        
    def add_postprocessor(self, field, f):
        self.postprocessors[field] = f

    def accept_field(self, field, fields):
        if len(fields) == 0:
            return True
        else:
            return (field in fields)
        
    def log(self, entry, log_sep = None):
        if self.accept_field(entry['level'].upper(), self.levels) and \
           self.accept_field(entry['source'], self.sources):
        
            self.print(entry, log_sep)

    def print(self, entry, log_sep = None):        
        if log_sep is None:
            log_sep = self.log_sep
        
        values = []
        lsep = len(self.sep)
        
        remaining_width = self.get_terminal_width()
        for col in self.columns:
            val = entry.get(col['field'], "---")
            f = self.preprocessors.get(col["field"], None)
            if f is not None:
                val = f(val)
            val = str(val)
            
            if col['length'] is not None:
                col['length'] = max(len(val), col['length'])
                remaining_width -= col['length']
            remaining_width -= 2 + lsep
            values.append(val)
        remaining_width = int(remaining_width / len(self.elastic_columns))
        
        all_lines = []
        format_strings = []
        max_lines_nb = 0
        for i,col in enumerate(self.columns):
            width = col['length'] if col['length'] is not None else remaining_width
            lines = values[i].split("\n")
            lines = [ l for line in lines for l in textwrap.wrap(line,width)]
            format_string ="{{:{}{}}}".format(col['align'], width)
            format_strings.append(format_string)
            max_lines_nb = max(max_lines_nb, len(lines))
            all_lines.append(lines)

        if self.skip_line: max_lines_nb += 1
   
        for i in range(max_lines_nb):
            for j,col in enumerate(self.columns):
                lines = all_lines[j]
                if i < len(lines):
                    field = lines[i]
                else:
                    field = ""
                f = self.postprocessors.get(col["field"], None)
                msg = format_strings[j].format(field)
                if f is not None:
                    msg = f(field, msg)
                print(self.sep + " " + msg + " ", end = '')
            print()

        if log_sep is not None:
            self.draw_line(log_sep)


def postprocess_color(colors, default_color = "white"):
    def f(key, field):
        color = colors.get(key, default_color)
        if isinstance(color, list):
            attrs = [] if len(color) == 1 else color[1:]
            return colored(field, color[0], attrs = attrs)
        elif isinstance(color, str):
            return colored(field, color)
    return f

def preprocess_time():
    t0 = int(time.time())
    return (lambda t: t - t0)
   
if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument('--broker-list', type=str,
                        help="The broker list. It could be either \n"
                        " - a filepath : containing a comma separated list"
                        " of brokers\n"
                        " - a comma separated list of brokers, e.g. "
                        " localhost:9091,localhost:9092\n",
                        required=True)
    parser.add_argument('--logs_topic', type=str,
                        default=default_log_topic,
                        help='The topic for listening to logs')
    parser.add_argument('--levels',
                        nargs='+',
                        help='list of displayed levels (empty = all)',
                        default = [])
    parser.add_argument('--sources',
                        nargs='+',
                        help='list of displayed sources (empty = all)',
                        default = [])
    args = parser.parse_args()
    
    consumer = KafkaConsumer(args.logs_topic,
                             bootstrap_servers=args.broker_list)


    logger = Logger(levels=args.levels, sources=args.sources)
    
    logger.add_preprocessor("t", preprocess_time())
    
    logger.add_postprocessor("level", postprocess_color({
        "DEBUG":    [ "grey" ],
        "INFO":     [ "green" ],
        "WARNING":  [ "yellow" ],
        "ERROR":    [ "red" ],
        "CRITICAL": [ "red", "blink"]
    }))
    
    logger.add_postprocessor("source", postprocess_color({
        "collector": [ "blue" ],
        "estimator": [ "magenta" ],
        "predictor": [ "yellow" ],
        "learner":   [ "cyan" ]
    }))
    
    for m in consumer:
        msg = json.loads(m.value.decode('utf8'))
        logger.log(msg)
