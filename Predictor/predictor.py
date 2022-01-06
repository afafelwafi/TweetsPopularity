import numpy as np
import json                       # To parse and dump JSON
from kafka import KafkaConsumer   # Import Kafka consumer
from kafka import KafkaProducer   # Import Kafka producer
import pickle                     # Library to save and load ML models using pickle  
import os
import sys
from kafka.admin import KafkaAdminClient, NewTopic # Create topics

# Getting the current path of the project
current_path = os.getcwd()

class Predictor :

    def __init__(self, T_obs, model, threshold) :
        """
        Constructs a predictor object, caracterized by its observation window T_obs, and associated with a ML model

        Args:
            self: the predictor object
            T_obs: int
                the observation windows (e.g 300, 600, etc.)
            model: object of type ML model
                the ML model associated with the given predictor, received from the learner, possessing a predict() method
            threshold: int
                if the size predicted is above the threshold, an alert is send to the dashboard

        Return:
            The predictor constructed
        """
        self.T_osb = T_obs
        self.model = model
        self.threshold = threshold


    def create_sample(self, parameters_msg, size_msg) :
        """
        Computes the variables X, W necessary to create a message of type sample to be sent to the samples topic

        Args:
            self: the predictor object
            parameters_msg : dict
                message of type paramaters received by the estimator in the topic cascade_properties
            size_msg: dict
                message of type size received by the collector in the topic cascade_properties

        Return:
            X : list
                list of input features like [beta, n_star, G1]
            W : float
                true Omega coefficent, i.e. the target to learn
        """
        n_tot_true = size_msg['n_tot']
        n_obs = parameters_msg['n_obs']
        _, beta, n_star_estimated, G1 = parameters_msg['params']
        # Using the formula N_tot = n + W * (G1 / (1 - n_star)), we retrieve W
        W_true = (n_tot_true - n_obs) * ((1 - n_star_estimated)/G1)
        X = [beta, n_star_estimated, G1] # Features to be used by the learner
        return X, W_true

    def predict(self, parameters_msg) :
        """
        Computes the predicted total length of a cascade using the ML model received by the learner for a given window

        Args:
            self: the predictor object
            parameters_msg : dict
                message of type paramaters received by the estimator in the topic cascade_properties

        Return:
            n_tot_predicted : int
                predicted total length of a cascade
        """
        n_obs = parameters_msg['n_obs']
        _, beta, n_star_estimated, G1 = parameters_msg['params']
        X = [beta, n_star_estimated, G1]
        W_predicted = self.model.predict(np.array(X).reshape(1, -1))[0]
        n_tot_predicted = n_obs + W_predicted * (G1 / (1 - n_star_estimated))
        return n_tot_predicted

    def compute_stat(self, parameters_msg, size_msg) :
        """
        Computes the Absolute Relative Error (ARE) given a predicted size of a cascade and its real length

        Args:
            self: the predictor object
            parameters_msg : dict
                message of type paramaters received by the estimator in the topic cascade_properties
            size_msg: dict
                message of type size received by the collector in the topic cascade_properties

        Return:
            ARE : float
                Absolute Relative Error (ARE) (ARE = |n_tot - n_true| / n_true )
        """
        n_tot_predicted = self.predict(parameters_msg)
        n_tot_true = size_msg['n_tot']
        ARE = abs((n_tot_predicted - n_tot_true)/n_tot_true)
        return ARE

if __name__ == '__main__' :

    # Checking if a parameters file has been passed as an argument in the terminal
    if len(sys.argv) != 2 :
         print("Usage " + sys.argv[0] + " <config-filename>")
         exit()
    else :
        # We use two lists of input and output topics
        in_topics=[]
        out_topics=[]
        # Getting the parameters from the txt parameters file
        with open(current_path + "/" + str(sys.argv[1])) as f :
            for line in f :
                # Skipping comments, section titles and blank lines
                if line[0] not in ['#','[', ' '] :
                    # The strip method allow to get rid of spaces and quotoation marks (" " and ' ') characters in the begining of the string
                    param = list(map(lambda x: x.strip(' \' \n'), line.split('=')))
                    if param[0] == 'brokers' : brokers = param[1]
                    elif param[0] == 'in_1' : in_topics.append(param[1])
                    elif param[0] == 'in_2' : in_topics.append(param[1])
                    elif param[0] == 'out_1' : out_topics.append(param[1])
                    elif param[0] == 'out_2' : out_topics.append(param[1])
                    elif param[0] == 'out_3' : out_topics.append(param[1])
                    elif param[0] == 'size_threshold' : size_threshold = int(param[1])
    
    # Construction of the Kafka consumer
    consumer = KafkaConsumer(in_topics[0], in_topics[1],                 # Topics names
    bootstrap_servers = brokers,                                         # List of brokers
    key_deserializer= lambda v: int(v.decode())                          # How to deserialize a key (if any)
    )

    # Construction of the Kafka producer
    producer = KafkaProducer(
    bootstrap_servers = brokers,                                        # List of brokers
    #key_serializer=str.encode                                           # How to serialize the key
    )

    # We use a dictionnary of dictionnaries to store the pairs (parameters_msg, size_msg) corresponding to the same
    # observation window T_obs and the same cascade cid. The keys of the level-1 dict are the T_obs while the keys of
    # level-2 dict are the cascade ids (cid).
    # parameters_msg : value of a message of type parameters received from the estimator through the topic cascade_properties,
    # containing the values of features to be used by the learner.
    # size_msg : value of a message of type size received from the collector through the topic cascade_properties, containing
    # the final size of a cascade.
    # e.g sample_msgs = {'600' : {'tw31245' : [parameters_msg, size_msg], 'tw31246' : ...}, '1200' : {...}}
    sample_msgs = {}

    # We use a dictionnary to store the predictors, which keys are the T_obs.
    # e.g predictors : {'600' : <predictor_object>, ...}
    predictors = {}

    for msg in consumer :                                               # Blocking call waiting for a new message
        # Case of a message coming from the cascade_properties topic (either a message of type parameters or type size)
        if msg.topic == in_topics[0] :                                  
            properties_msg = json.loads((msg.value).decode('utf-8'))    # We deserialize the message
            key = str(msg.key)
            cid = properties_msg['cid']

            # If the key (T_obs) has never been observed before, it is created in the sample_msgs level-1 dict
            if key not in sample_msgs.keys() : 
                sample_msgs[key] = {cid : [properties_msg]}
            # If the key (cid) has never been observed before, it is created in the sample_msgs level-2 dict
            elif (key in sample_msgs.keys()) and (cid not in sample_msgs[key].keys()) :
                sample_msgs[key][cid] = [properties_msg]
            # If both the T_obs key and cid key have been observed before, we store the value in the corresponding level-2 dict
            elif (key in sample_msgs.keys()) and (cid in sample_msgs[key].keys()) :
                sample_msgs[key][cid].append(properties_msg)            
            
            # If the key (T_obs) has never been observed before, it is created in the predictors dict
            if key not in predictors.keys() :
                predictors[key] = Predictor(msg.key, None, size_threshold)
            # If the key (T_obs) has been observed before, and if the current message received is a parameters type message 
            # (i.e a message from the cascade properties topic of length 6) we can predict the final size of the cascade.
            elif (key in predictors.keys()) and predictors[key].model and len(properties_msg) == 6 :
                n_tot_predicted = predictors[key].predict(properties_msg)
                # If the size predicted is above the threshold defined, an alert is sent to the dashboard
                if n_tot_predicted > predictors[key].threshold :
                    # Creation and encoding of the alert message
                    alert_msg = {'type': 'alert', 'cid': cid, 'msg' : properties_msg['msg'], 'T_obs': msg.key, 'n_tot' : n_tot_predicted}
                    alert_msg_encoded = json.dumps(alert_msg).encode('utf-8')
                    producer.send(out_topics[1], key=None, value = alert_msg_encoded)
                    print("\n---------------------------alert message-------------------")
                    print(alert_msg)
                    print("---------------------------------------------------\n")

            # If the list corresponding to the key cid in the level-2 dict of the sample_msgs dict contains two elements
            # (i.e a size_msg and a parameters_msg), we can create the corresponding sample using the create_sample method.
            if len(sample_msgs[key][cid]) == 2 :
                # Cheking the lengths to determine which element is the size_msg and which one is the parameters_msg
                if len(sample_msgs[key][cid][0]) <  \
                    len(sample_msgs[key][cid][1]) :
                    # Creation and encoding of the sample
                    X, W_true = predictors[key].create_sample(sample_msgs[key][cid][1], sample_msgs[key][cid][0])
                    sample_msg = {'type' : 'sample', 'cid' : cid, 'X' : X, 'W' : W_true}
                    sample_msg_encoded = json.dumps(sample_msg).encode('utf-8')
                    key_encoded = str.encode(key)
                    producer.send(out_topics[0], key = key_encoded, value = sample_msg_encoded)
                    print('\n ---------------------sample message---------------------')
                    print(f'T_obs : {key}')
                    print(f'cid : {cid}')
                    print(f'sample sent : {sample_msg}')
                    print(f'n_obs : {sample_msgs[key][cid][1]["n_obs"]}')
                    print(f'n_predicted : {sample_msgs[key][cid][1]["n_obs"] + sample_msgs[key][cid][1]["n_supp"]}')
                    print(f'n_true : {sample_msgs[key][cid][0]["n_tot"]}')
                    print('------------------------------------------')
                    # If we have access to a model for that specific winodwd observation, we can compute the ARE 
                    # and create a message of type stat.
                    if (key in predictors.keys()) and predictors[key].model :
                        ARE = predictors[key].compute_stat(sample_msgs[key][cid][1], sample_msgs[key][cid][0])
                        stat_msg = {'type': 'stat', 'cid': cid, 'T_obs': msg.key, 'ARE' : ARE}
                        stat_msg_encoded = json.dumps(stat_msg).encode('utf-8')
                        producer.send(out_topics[2], key=None, value = stat_msg_encoded)
                        print("\n ---------------------------stat message-------------------")
                        print(stat_msg)
                        print("--------------------------------------------- \n")
                else :
                    # Creation and encoding of the sample
                    X, W_true = predictors[key].create_sample(sample_msgs[key][cid][0], sample_msgs[key][cid][1])
                    sample_msg = {'type' : 'sample', 'cid' : cid, 'X' : X, 'W' : W_true}
                    sample_msg_encoded = json.dumps(sample_msg).encode('utf-8')
                    key_encoded = str.encode(key)
                    producer.send(out_topics[0], key = key_encoded, value = sample_msg_encoded)
                    print('\n ---------------------sample message---------------------')
                    print(f'T_obs : {key}')
                    print(f'cid : {cid}')
                    print(f'sample sent : {sample_msg}')
                    print(f'n_obs : {sample_msgs[key][cid][0]["n_obs"]}')
                    print(f'n_predicted : {sample_msgs[key][cid][0]["n_obs"] + sample_msgs[key][cid][0]["n_supp"]}')
                    print(f'n_true : {sample_msgs[key][cid][1]["n_tot"]}')
                    print('------------------------------------------ \n')
                    # If we have access to a model for that specific winodwd observation, we can compute the ARE 
                    # and create a message of type stat.
                    if (key in predictors.keys()) and predictors[key].model :
                        ARE = predictors[key].compute_stat(sample_msgs[key][cid][0], sample_msgs[key][cid][1])
                        stat_msg = {'type': 'stat', 'cid': cid, 'T_obs': msg.key, 'ARE' : ARE}
                        stat_msg_encoded = json.dumps(stat_msg).encode('utf-8')
                        producer.send(out_topics[2], key=None, value = stat_msg_encoded)
                        print("\n ---------------------------stat message-------------------")
                        print(stat_msg)
                        print("--------------------------------------------- \n")
        
        # Case of a message coming from the models topic
        elif msg.topic == in_topics[1] :
            # Unpickling the model
            model = pickle.loads(msg.value)
            key = str(msg.key)
            
            
            # If the key (T_obs) has never been observed before, it is created in the predictors dict
            if key not in predictors.keys() :
                predictors[key] = Predictor(msg.key, model, size_threshold)
            # Else, the model is updated
            else :
               predictors[key].model = model 




