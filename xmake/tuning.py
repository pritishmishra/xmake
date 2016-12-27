###############################################################################
# ARTIFACT DEPLOYER
###############################################################################
# timeout
AD_TIMEOUT = 600000 # milliseconds

###############################################################################
# NEXUS staging request settings
###############################################################################
# default
# if we do all the attemps the total delay will be a sum of arithmetic series
# Sn = n*(U1+Un)/2
# => (REQ_ATTEMPTS-1) x DELAY_BETWEEN_REQ_ATTEMPTS x REQ_ATTEMPTS / 2
REQ_ATTEMPTS = 10
DELAY_BETWEEN_REQ_ATTEMPTS = 5 #seconds
# max total waiting is (10-1)x5x10/2 = 225s

#close
# if we do all the attemps the total delay will be a sum of arithmetic series
# Sn = n*(U1+Un)/2
# => (CLOSE_REQ_ATTEMPTS-1) x CLOSE_DELAY_BETWEEN_REQ_ATTEMPTS x CLOSE_REQ_ATTEMPTS / 2
CLOSE_REQ_ATTEMPTS = 11
CLOSE_DELAY_BETWEEN_REQ_ATTEMPTS = 60 #seconds
# max total waiting is (11-1)x60x11/2 = 3300s

#promote
# if we do all the attemps the total delay will be a sum of arithmetic series
# Sn = n*(U1+Un)/2
# => (PROMOTE_REQ_ATTEMPTS-1) x PROMOTE_DELAY_BETWEEN_REQ_ATTEMPTS x PROMOTE_REQ_ATTEMPTS / 2
PROMOTE_REQ_ATTEMPTS = 11
PROMOTE_DELAY_BETWEEN_REQ_ATTEMPTS = 60 #seconds
# max total waiting is (11-1)x60x11/2 = 3300s

#deploy
# if we do all the attemps the total delay will be a sum of arithmetic series
# Sn = n*(U1+Un)/2
# => (DEPLOY_FILE_REQ_ATTEMPTS-1) x DEPLOY_FILE_DELAY_BETWEEN_REQ_ATTEMPTS x DEPLOY_FILE_REQ_ATTEMPTS / 2
DEPLOY_FILE_REQ_ATTEMPTS = 4
DEPLOY_FILE_DELAY_BETWEEN_REQ_ATTEMPTS = 120 #seconds
# max total waiting is (4-1)x120x4/2 = 720s
