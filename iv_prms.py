import numpy as np
import scipy as sp

class IVprm(object):
    """
    Calculate basic solar cell paramters from a I-V or j-V curve including
    Voc, Jsc, Isc, FF, PCE, Rs, and Rsh.
    """
    def __init__(self, v, j, area, current=False, reversed_j=False):
        """
        Accepts np.array and float, not DataFrame.
        
        Args:
            v: A list of voltage [V], (np.array)
            j: If current = False, a list of current_density [mA/cm^2]
                (np.array), else, current [A].
            area: Area of cell or module [cm^2] (float)
            current: If False, j is read as current density [mA/cm^2],
                else, current [A]. Default is False
            reversed_j: If true, the sign of the current is reversed,
                        just like in Yokohama.
        """
        
        PINT = 100  #[mW/cm^2]

        self.v = v
        self.area = float(area)

        if not reversed_j:
            j = -j

        if current:
            self.j = j/self.area * 1000  #[mA] -> [A]
            self.i = j
        else:
            self.j = j
            self.i = j * self.area / 1000  #[A] -> [mA]
        
        self.power = self.v * self.i  #[W]

        self.voc = find_zero_cross(self.v,self.j)
        self.jsc = find_zero_cross(self.j,self.v)
        self.isc = self.jsc * self.area / 1000  #[A]

        self.mpp = self.power.max()

        self.ff = self.mpp/(self.voc * self.isc)
        self.pce = (self.mpp * 1000)/ self.area / PINT * 100  # calcurate in mW/cm^2 unit. Finally the value is converted to %.

        if (self.voc==0) or (self.jsc==0):
            self.ff = 0
            self.pce = 0
        
        try:
            self.rs = find_rs(self.v, self.j)  #[Ohm cm^2]
            self.rsh = find_rsh(self.v, self.j)  #[Ohm cm^2]

        except:
            print 'error at Rs, Rsh fitting'
            self.rs = 0
            self.rsh = 0

def find_zero_cross(x, y):
    """accepts np.array, not DataFrame"""

    try:
        zp = np.where(y[:-1] * y[1:] <= 0)[0][0]  #make a list of A[x] * A[x -1] without usinf "for" loop in original python.
        m = np.polyfit(x[(zp - 1):(zp + 1)], y[(zp -1):(zp + 1)], 1)
        zc = -m[1]/m[0]  #For y = ax + b and y = 0, then x = -b/a.

    except:
        print 'error at zero_cross'
        zc = 0

    return zc

def find_rs(v, j):
    """Calculate series resistance from a j-V list
    
    Args:
        v: a list of voltage [V](np.array)
        j: a list of current density [mA/cm^2]
        
    Returns:
        A float number of series resistance [Ohm cm^2].
    """
    v_s, j_s = np.sort([v, j], axis=1)
    m = np.polyfit(v_s[-10:], j_s[-10:], 1)
    return 1/abs(m[0]) * 1000  #[Ohm cm^2]

def find_rsh(v, j):
    """Calculate shant resistance from a j-V list
    
    Args:
        v: a list of voltage [V] (np.array)
        j: a list of current density [mA/cm^2]
        
    Returns:
        A float number of shant resistance [Ohm cm^2]
    """

    zp = sp.where(v[:-1] * v[1:] <= 0)[0][0]  #make a list of A[x] * A[x -1] without usinf "for" loop in original python.
    m = np.polyfit(v[(zp - 5):(zp + 5)], j[(zp -5):(zp + 5)], 1)
    return 1/abs(m[0]) * 1000  #[Ohm cm^2]
