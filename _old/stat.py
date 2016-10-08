import math
import random


levels = [max(-12,min(12, int(random.normalvariate(-2.0, sigma=4)))) for n in range(20)]

def weight(lv):
    return lv*abs(lv) + 5*5

def weight(lv):
    def expw(lv):
        return abs(lv)
        #return math.sqrt(math.sqrt(abs(lv) * lv * lv))
    if lv < -6:
        return 0
    if lv < 0:
        return math.e ** (lv / 2)
    return math.e ** (lv / 3.5)
    '''
    if lv > 0:
        return expw(lv+1)
    elif lv < 0:
        return 1 / expw(lv-1)
    else:
        return 1
    '''
def lvadj(c, slv, lv):
    return lv
    return lv - (slv / c) - 3.0
    
slv = sum(lv for lv in levels)
adj_levels = [lvadj(len(levels), slv, lv) for lv in levels]
s = sum(weight(lv) for lv in adj_levels)
sadj = sum(lv for lv in adj_levels)

for lv, adj in zip(levels, adj_levels):
    print('{:+3d} {:f} {:+3d} {:f} {:f} {:f}'.format(slv, sadj, lv, adj, weight(adj), weight(adj) / s))
    