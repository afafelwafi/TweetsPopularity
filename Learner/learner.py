import numpy as np
import json
import sys
import os
import pandas as pd               # To parse and dump JSON
from kafka import KafkaConsumer   # Import Kafka consumer
from kafka import KafkaProducer   # Import Kafka producer
import pickle                     # Library to save and load ML regressors using pickle
import pandas as pd

# scikit learn
from  sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import GridSearchCV

# Getting the current path of the project
current_path = os.getcwd()

class Learner :
    def __init__(self, T_obs, samples, model, counter=1):
        self.T_obs = T_obs
        self.samples = samples
        if model == 'RandomForest' :
            self.model = RandomForestRegressor()
        elif model == 'GradientBoosting' :
            self.model = GradientBoostingRegressor()
        self.counter = counter

    def _reset_model(self) :
        if model == 'RandomForest' :
            self.model = RandomForestRegressor()
        elif model == 'GradientBoosting' :
            self.model = GradientBoostingRegressor()
    
    def fit(self):
        grid_parameters = {'max_depth': [10],
                            'min_samples_leaf': [1, 2, 4],
                            'min_samples_split': [2, 5, 10]
                            }
        self._reset_model()
        reg = GridSearchCV(self.model, grid_parameters, cv=3)
        X = self.samples.iloc[:, :-1].values
        y = self.samples.iloc[:, -1].values
        reg.fit(X, y)
        self.model = reg.best_estimator_


if __name__ == '__main__' :
    if len(sys.argv) != 2 :
         print("Usage" + sys.argv[0] + " <config-filename>")
         exit()
    else :
        with open(current_path + "/" + str(sys.argv[1])) as f :
            for line in f :
                if line[0] not in ['#','[', ' '] :
                    param = list(map(lambda x: x.strip(' \' \n'), line.split('=')))
                    if param[0] == 'brokers' : brokers = param[1]
                    elif param[0] == 'in_' : in_ = param[1]
                    elif param[0] == 'out_' : out_ = param[1]
                    elif param[0] == 'treshold_to_learn' : treshold_to_learn = float(param[1])
                    elif param[0] == 'model' : model = param[1]


    consumer = KafkaConsumer(in_,                               # Topic name
    bootstrap_servers = brokers,                                # List of brokers
    key_deserializer= lambda v: int(v.decode()),                # How to deserialize a key (if any)
    value_deserializer=lambda v: json.loads(v.decode('utf-8'))  # How to deserialize sample messages
    )

    producer = KafkaProducer(
    bootstrap_servers = brokers,                                # List of brokers passed from the command line
    key_serializer=str.encode,                                  # How to serialize the key
    value_serializer=lambda v: pickle.dumps(v)                 # How to serialize a model
    )

    learners={}                                             # for each key a learner

    for msg in consumer :
        print("\n -----------------Sample in------------------------")
        samples_msg = msg.value                                   
        key = str(msg.key)
        X = samples_msg['X']
        y = samples_msg['W']
        sample = pd.DataFrame(np.array(X + [y]).reshape(1, -1), columns=['beta','n_star','G1', 'W'])

        if key not in learners.keys() :
            print(f'Created a new learner for key : {key}')
            learner = Learner(key, sample, model)
            learners[key] = learner

        else :
            #print(f'samples df before append = {learners[key].samples}')
            print(f'Appended the sample to the dataframe for key: {key}')
            learners[key].samples = learners[key].samples.append(sample, ignore_index=True)
            learners[key].counter += 1
            #print(f'samples df after append = {learners[key].samples}')
            if learners[key].counter >= treshold_to_learn :
                print(f'Time to learn for key : {key} !')
                print(f'counter = {learners[key].counter} !')
                learners[key].fit()
                learners[key].counter = 0
                producer.send(out_, key=key, value=learners[key].model)
                print(f'Model for key : {key} succesfully sent to the predictor')
                print('-------------------------------------------')