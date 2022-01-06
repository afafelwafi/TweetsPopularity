# Basic libraries
import numpy as np
import os
import sys

# Libraries for handling kafka messages
import ast                   
import json                       # To parse and dump JSON
from kafka import KafkaConsumer   # Import Kafka consumer
from kafka import KafkaProducer   # Import Kafka producer
from time import sleep

# Functions to process cascades
from hawkes_process import compute_MAP, compute_MLE, prediction

# Getting the current path of the project
current_path = os.getcwd()

class Estimator:

    def __init__(self, brokers, in_, out_, prior_param, max_n_star, alpha, mu, estimator_type):
        """
        Constructs an estimator object, caracterized by the prior parameters of the MAP estimator (if used) and
        other parameters specific to the Hawkes structure (max_n_star, alpha, mu etc.)

        Args:
            self : the estimator object
            brokers : str
                the kafka brokers used to construct the consumer and the producer associated with the estimator
            in_: str
                the name of the input topic where messages of type serie have to be collected
            out_ : str
                the name of the output topic where messages of type parameters have to be posted
            prior_params : list (mu_p, mu_beta, sig_p, sig_beta, corr) of hyper parameters of the prior
                        -- where:
                        --   mu_p:     is the prior mean value of p
                        --   mu_beta:  is the prior mean value of beta
                        --   sig_p:    is the prior standard deviation of p
                        --   sig_beta: is the prior standard deviation of beta
                        --   corr:     is the correlation coefficient between p and beta
            alpha : float
                power parameter of the power-law mark distribution of the magnitudes of the tweets
            mu : float
                min value parameter of the power-law mark distribution
            estimator_type : str
                type of estimator to be used (MAP or MLE)
            

        Return:
            The estimator constructed
        """
        self.brokers = brokers
        self.in_ = in_
        self.out_ = out_
        self.prior_param = prior_param
        self.max_n_star = max_n_star
        self.alpha = alpha
        self.mu = mu
        self.estimator_type = estimator_type

    def process_cascade(self, cascade):
        """
        Computes the estimate of the parameters of the Hawkes model (p, beta) and the predicted total size of the cascade
        without refinements (i.e W=1 here), then constructs a message of type parameters.

        Args:
            self : the estimator object
            cascade : dict
                message of type cascade received from the collector in the topic cascade_size
            
        Return:
            T_obs: int
                the observation windows (e.g 300, 600, etc.)
            parameters_msg : dict
                message of type parameters

        """
        # The actual time serie, i.e a list of pairs (t,m) of timestamp t and magnitude m
        tweets = cascade['tweets']
        # Current size of the cascade
        n_obs = len(tweets)
        # (cascade_current_size,2) numpy array containing marked time points (t_i,m_i)
        history = np.array(list(map(lambda x:list(x), cascade['tweets']))).reshape((n_obs, 2))
        # Length in seconds of the observation window of the cascade.
        T_obs = cascade['T_obs']
        # Current time
        T_current = history[0, 0] + T_obs
        # Identifier of the given cascade.
        cid = cascade['cid']
        # Message of the original tweet
        msg = cascade['msg']

        if self.estimator_type == 'MAP' :
            # Estimation of the parameters (p, beta) using the MAP estimator
            _, params = compute_MAP(history, T_current, self.alpha, self.mu, self.prior_param, self.max_n_star)
            # Computation of the predicted number of future retweets to come
            n_tot_predicted, n_star_predicted, G1 = prediction(params, history, self.alpha, self.mu, T_current)
            n_supp_predicted = int(n_tot_predicted - n_obs)
            # Adding n_star_predicted and G1 to the list of features that will be passed to the predictor
            params_enriched = params.tolist() + [n_star_predicted, G1]
        elif self.estimator_type == 'MLE' :
            # Estimation of the parameters (p, beta) using the MLE estimator
            _, params = compute_MLE(history, T_current, self.alpha, self.mu, np.array([0.0001, 1./60]), self.max_n_star)
            # Computation of the predicted number of future retweets to come
            n_tot_predicted, n_star_predicted, G1 = prediction(params, history, self.alpha, self.mu, T_current)
            n_supp_predicted = int(n_tot_predicted - n_obs)
            # Adding n_star_predicted and G1 to the list of features that will be passed to the predictor
            params_enriched = params.tolist() + [n_star_predicted, G1]
        
        # Construction of the message of type parameters
        parameters_msg = {'type' : 'parameters', 'cid' : cid, 'msg' : msg, 'n_obs' :n_obs, 'n_supp' : n_supp_predicted, 'params' : params_enriched}

        return T_obs, parameters_msg



if __name__ == '__main__' :
    # Checking if a parameters file has been passed as an argument in the terminal
    if len(sys.argv) != 2 :
         print("Usage " + sys.argv[0] + " <config-filename>")
         exit()
    else :
        # Getting the parameters from the txt parameters file
        with open(current_path + "/" + str(sys.argv[1])) as f :
            for line in f :
                # Skipping comments, section titles and blank lines
                if line[0] not in ['#','[', ' '] :
                    # The strip method allow to get rid of spaces and quotoation marks (" " and ' ') characters in the begining of the string
                    param = list(map(lambda x: x.strip(' \' \n'), line.split('=')))
                    if param[0] == 'brokers' : brokers = param[1]
                    elif param[0] == 'in_' : in_ = param[1]
                    elif param[0] == 'out_' : out_ = param[1]
                    elif param[0] == 'prior_params' :
                        prior_param = list(map(lambda x: float(x), param[1].strip(' [] \n').split(', ')))
                    elif param[0] == 'max_n_star' : 
                        max_n_star = float(param[1])
                    elif param[0] == 'alpha' : alpha = float(param[1])
                    elif param[0] == 'mu' : mu = float(param[1])
                    elif param[0] == 'estimator_type' : estimator_type = param[1]

    
    # Construction of the estimator object
    _estimator = Estimator(brokers, in_, out_, prior_param, max_n_star, alpha, mu, estimator_type)

    # Construction of the Kafka consumer
    consumer = KafkaConsumer(_estimator.in_,                     # Topic name
    bootstrap_servers = _estimator.brokers,                      # List of brokers
    value_deserializer=lambda v:ast.literal_eval(v.decode('utf-8'))
    )

    # Construction of the Kafka producer
    producer = KafkaProducer(
    bootstrap_servers = _estimator.brokers,                   # List of brokers
    value_serializer=lambda v: json.dumps(v).encode('utf-8'), # How to serialize the value to a binary buffer
    key_serializer=str.encode                                 # How to serialize the key
    )

    for cascade in consumer:                                                     # Blocking call waiting for a new message
        T_obs, parameters_msg = _estimator.process_cascade(cascade.value)
        producer.send(_estimator.out_, key = str(T_obs), value = parameters_msg) # Send a new message to topic
        print('\n -------------------------------------------------')
        print(f'message of type parameters sent : {parameters_msg}')
        print(f'key of the message : {str(T_obs)}')
        print('--------------------------------------------------- \n')


    



