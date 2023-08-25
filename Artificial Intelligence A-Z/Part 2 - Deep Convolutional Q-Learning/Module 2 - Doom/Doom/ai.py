# AI for Doom



# Importing the libraries
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.autograd import Variable

# Importing the packages for OpenAI and Doom
import gym
from gym.wrappers import SkipWrapper
from ppaquette_gym_doom.wrappers.action_space import ToDiscrete

# Importing the other Python files
import experience_replay, image_preprocessing



# Part 1 - Building the AI

# Making the brain

class CNN(nn.Module):
    def __init__(self, number_actions):
        super(CNN, self).__init__()
        self.convolution1 = nn.Conv2d(in_channels = 1, out_channels = 32, kernel_size = 5)   #input images to detect features
        self.convolution2 = nn.Conv2d(in_channels = 32, out_channels = 32, kernel_size = 3)  
        self.convolution3 = nn.Conv2d(in_channels = 32, out_channels = 64, kernel_size = 2)
        self.fc1= nn.Linear(in_features = self.countNeurons((1, 80, 80)) , out_features = 40)            #full connections
        self.fc2 = nn.Linear(in_features=40, out_features= number_actions)
    
    def countNeurons(self, image_dim):
        x = Variable(torch.rand(1, *image_dim))
        x = F.relu(F.max_pool2d(self.convolution1(x), 3, 2))
        x = F.relu(F.max_pool2d(self.convolution2(x), 3, 2))
        x = F.relu(F.max_pool2d(self.convolution3(x), 3, 2))
        return x.data.view(1, -1).size(1)
    
    def forward(self, x):
        x = F.relu(F.max_pool2d(self.convolution1(x), 3, 2))
        x = F.relu(F.max_pool2d(self.convolution2(x), 3, 2))
        x = F.relu(F.max_pool2d(self.convolution3(x), 3, 2))
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x
    
    
    
class SoftmaxBody(nn.Module):
    def __init__(self, T):
        super(SoftmaxBody, self).__init()
        self.T = T
        
    def forward(self, outputs):
        probs = F.softmax(outputs * self.T) #creates the prob variable to apply the softmax func
        actions = probs.multinomial() #action passed to the body(the game movements)
        return actions
    
# MAKING THE AI

class AI:
    def __init__(self, brain, body):
        self.brain = brain
        self.body = body
        
    def __call__(self, inputs):
        input = Variable(torch.from_numpy(np.array(inputs, dtype = np.float32)))
        # The code up is the conversion of the input images to the brain, making them in the right format
        #The format is from image to numpy array, then converted to torch tensor and finally asigning this value to a variable
        output = self.brain(input) #output signal of the brain to propagate it to the body in oder to make the best action
        actions = self.body(output)
        return actions.data.numpy()
    
#Part 2 - Training the AI with Deep Convolutional Learning

# Getting the Doom Enviroment
doom_env = image_preprocessing.PreprocessImage(SkipWrapper(4)(ToDiscrete("minimal")(gym.make("ppaquette/DoomCorridor-v0"))), width = 80, height = 80, grayscale = True)
doom_env = gym.wrappers.Monitor(doom_env, "videos", force = True)
number_actions = doom_env.action_space.n

#   BUILDING AN AI WITH THE CLASSES AND OBJECTS CREATED BEFORE

cnn = CNN(number_actions)
softmax_body = SoftmaxBody(T = 1)
ai = AI(brain = cnn, body = softmax_body)

#Setting up experience replay with elegibillity trace (rewards from multiple steps)
n_steps = experience_replay.NStepPocess(env=doom_env, ai = ai, n_step=10)
memory = experience_replay.ReplayMemory(n_steps = n_steps, capacity= 10000)
def eligibility_trace(batch):
    gamma = 0.99
    inputs = []
    targets = []
    for series in batch:
        input = Variable(torch.from_numpy(np.array([series[0].state, series[-1].state], dtype = np.float32)))
        output = cnn(input)
        cumul_reward = 0.0 if series[-1].done else output[1].data.max()
        for step in reversed(series[:-1]):
            cumul_reward = step.reward + gamma * cumul_reward
        state = series[0].state
        target = output[0].data
        target[series[0].action] = cumul_reward
        inputs.append(state)
        targets.append(target)
    return torch.from_numpy(np.array(inputs, dtype = np.float32)), torch.stack(targets)
         
# Making the moving avergage on 100 steps to keep track o the average during the training
class MA:
    def __init__(self, size ):
        self.list_of_rewards = []
        self.size = size
    
    def add(self, rewards):
        if isinstance(rewards, list):
            self.list_of_rewards += rewards
        else:
            self.list_of_rewards.append(rewards)
        while len(self.list_of_rewards)> self.size:
            del self.list_of_rewards[0]
    def average(self):
        return np.mean(self.list_of_rewards)
        
ma = MA(100)           


# Training th ai

loss = nn.MSELoss()
optimizer = optim.Adam(cnn.parameters(), lr = 0.001)
nb_epochs = 100
for epoch in range(1, nb_epochs + 1):
    memory.run_steps(200)
    for batch in memory.sample_batch(128):
        inputs, targets = eligibility_trace(batch)
        inputs, targets = Variable(inputs), Variable(targets)
        predictions = cnn(inputs)
        loss_error = loss(predictions, targets)
        optimizer.zero_grad()
        loss_error.backward()
        optimizer.step()
    rewards_steps = n_steps.rewards_steps()
    ma.add(rewards_steps)
    avg_reward = ma.average()

    print("Epoch: %s Average Reward: %s" % (str(epoch),str(avg_reward)))
        
        
                

        
