#  TweetsPopularity
The subject was chosen in **my 3rd year in school** to cover the whole landscape, from abstract concepts of statistics to very practical skills in computer sciences.

### Project's idea:
We want is to detect as soon as possible tweets that are likely to become popular, where popularity of a tweet is defined as the number of times this tweet will be retweeted, i.e. forwarded by users to their followers. Because retweets propagate with a cascade effect, a tweet and all retweets it triggered, build up what is hereafter called a cascade. Once we are able to predict popularities of tweets, it is straight-forward to identify the most promising tweets with the highest expected popularity. So to summarize, the problem is to guess the final size of cascades, just by observing the beginning of these cascade during a given observation time window, like, say, the ten first minutes.

### Architechture:
![image](https://user-images.githubusercontent.com/54381332/149750291-3141be2c-7382-4e23-a0e2-11b59a2c0d6b.png)
