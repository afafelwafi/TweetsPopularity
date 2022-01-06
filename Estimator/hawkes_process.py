import numpy as np
import scipy.optimize as optim

# Function to compute the logelikelihood of the cascade given params.
def loglikelihood(params, history, t):
    """
    Returns the loglikelihood of a Hawkes process with exponential kernel
    computed with a linear time complexity
        
    params   -- parameter tuple (p,beta) of the Hawkes process
    history  -- (n,2) numpy array containing marked time points (t_i,m_i)  
    t        -- current time (i.e end of observation window)
    """
    
    p,beta = params    
    
    if p <= 0 or p >= 1 or beta <= 0.: return -np.inf

    n = len(history)
    mis = history[:,1]
    
    LL = (n-1) * np.log(p * beta)
    logA = -np.inf
    prev_ti, prev_mi = history[0]
    
    i = 0
    for ti,mi in history[1:]:
        if(prev_mi + np.exp(logA) <= 0):
            print("Bad value", prev_mi + np.exp(logA))
        
        logA = np.log(prev_mi + np.exp(logA)) - beta * (ti - prev_ti)
        LL += logA
        prev_ti,prev_mi = ti,mi
        i += 1
        
    logA = np.log(prev_mi + np.exp(logA)) - beta * (t - prev_ti)
    LL -= p * (np.sum(mis) - np.exp(logA))

    return LL


# Function to compute the MAP estimator of the parameters of the Hawkes process
def compute_MLE(history, t, alpha, mu,
                init_params=np.array([0.0001, 1./60]), 
                max_n_star = 1., display=False):
    """
    Returns the pair of the estimated loglikelihood and parameters (as a numpy array)

    history     -- (n,2) numpy array containing marked time points (t_i,m_i)  
    t           -- current time (i.e end of observation window)
    alpha       -- power parameter of the power-law mark distribution
    mu          -- min value parameter of the power-law mark distribution
    init_params -- initial values for the parameters (p,beta)
    max_n_star  -- maximum authorized value of the branching factor (defines the upper bound of p)
    display     -- verbose flag to display optimization iterations (see 'disp' options of optim.optimize)
    """
    
    # Define the target function to minimize as minus the loglikelihood
    target = lambda params : -loglikelihood(params, history, t)
    
    EM = mu * (alpha - 1) / (alpha - 2)
    eps = 1.E-8

    # Set realistic bounds on p and beta
    p_min, p_max       = eps, max_n_star/EM - eps
    beta_min, beta_max = 1/(3600. * 24 * 10), 1/(60. * 1)
    
    
    # Define the bounds on p (first column) and beta (second column)
    bounds = optim.Bounds(
        np.array([p_min, beta_min]),
        np.array([p_max, beta_max])
    )
    
    # Run the optimization
    res = optim.minimize(
        target, init_params,
        method='Powell',
        bounds=bounds,
        options={'xtol': 1e-8, 'disp': display}
    )
    
    # Returns the loglikelihood and found parameters
    return(-res.fun, res.x)

# Function to compute the MAP estimator of the parameters of the Hawkes process
def compute_MAP(history, t, alpha, mu,
                prior_params = [ 0.02, 0.0002, 0.01, 0.001, -0.1],
                max_n_star = 1):
    """
    Returns the pair of the estimated logdensity of a posteriori and parameters (as a numpy array)

    history      -- (n,2) numpy array containing marked time points (t_i,m_i)  
    t            -- current time (i.e end of observation window)
    alpha        -- power parameter of the power-law mark distribution
    mu           -- min value parameter of the power-law mark distribution
    prior_params -- list (mu_p, mu_beta, sig_p, sig_beta, corr) of hyper parameters of the prior
                -- where:
                --   mu_p:     is the prior mean value of p
                --   mu_beta:  is the prior mean value of beta
                --   sig_p:    is the prior standard deviation of p
                --   sig_beta: is the prior standard deviation of beta
                --   corr:     is the correlation coefficient between p and beta
    max_n_star   -- maximum authorized value of the branching factor (defines the upper bound of p)
    display      -- verbose flag to display optimization iterations (see 'disp' options of optim.optimize)
    """
    
    # Compute prior moments
    mu_p, mu_beta, sig_p, sig_beta, corr = prior_params
    sample_mean = np.array([mu_p, mu_beta])
    cov_p_beta = corr * sig_p * sig_beta
    Q = np.array([[sig_p ** 2, cov_p_beta], [cov_p_beta, sig_beta **2]])
    
    # Apply method of moments
    cov_prior = np.log(Q / sample_mean.reshape((-1,1)) / sample_mean.reshape((1,-1)) + 1)
    mean_prior = np.log(sample_mean) - np.diag(cov_prior) / 2.

    # Compute the covariance inverse (precision matrix) once for all
    inv_cov_prior = np.asmatrix(cov_prior).I

    # Define the target function to minimize as minus the log of the a posteriori density    
    def target(params):
        log_params = np.log(params)
        
        if np.any(np.isnan(log_params)):
            return np.inf
        else:
            dparams = np.asmatrix(log_params - mean_prior)
            prior_term = float(- 1/2 * dparams * inv_cov_prior * dparams.T)
            logLL = loglikelihood(params, history, t)
            return - (prior_term + logLL)
    
    EM = mu * (alpha - 1) / (alpha - 2)
    eps = 1.E-8

    # Set realistic bounds on p and beta
    p_min, p_max       = eps, max_n_star/EM - eps
    beta_min, beta_max = 1/(3600. * 24 * 10), 1/(60. * 1)
    
    # Define the bounds on p (first column) and beta (second column)
    bounds = optim.Bounds(
        np.array([p_min, beta_min]),
        np.array([p_max, beta_max])
    )
    
    # Run the optimization
    res = optim.minimize(
        target, sample_mean,
        method='Powell',
        bounds=bounds,
        options={'xtol': 1e-8}
    )
    # Returns the loglikelihood and found parameters
    return(-res.fun, res.x)

# Function to predict the final size of a cascade
def prediction(params, history, alpha, mu, t):
    """
    Returns the expected total numbers of points for a set of time points
    
    params   -- parameter tuple (p,beta) of the Hawkes process
    history  -- (n,2) numpy array containing marked time points (t_i,m_i)  
    alpha    -- power parameter of the power-law mark distribution
    mu       -- min value parameter of the power-law mark distribution
    t        -- current time (i.e end of observation window)
    """

    p,beta = params
    
    tis = history[:,0]
   
    EM = mu * (alpha - 1) / (alpha - 2)
    n_star = p * EM
    if n_star >= 1:
        raise Exception(f"Branching factor {n_star:.2f} greater than one")
    n = len(history)

    I = history[:,0] < t
    tis = history[I,0]
    mis = history[I,1]
    G1 = p * np.sum(mis * np.exp(-beta * (t - tis)))
    Ntot = n + G1 / (1. - n_star)
    return Ntot, n_star, G1