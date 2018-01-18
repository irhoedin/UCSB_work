import pylab as pl
import numpy as np

from matplotlib import rc

rc('text', usetex=True)
pl.rcParams['text.latex.preamble'] = [
    r'\usepackage{tgheros}',  # helvetica font
    r'\usepackage{sansmath}',  # math-font matching  helvetica
    r'\sansmath'  # actually tell tex to use it!
    r'\usepackage{siunitx}',  # micro symbols
    r'\sisetup{detect-all}',  # force siunitx to use the fonts
]

pl.figure(1, figsize=(6, 4))
ax = pl.axes([0.1, 0.1, 0.8, 0.7])
t = np.arange(0.0, 1.0 + 0.01, 0.01)
s = np.cos(2 * 2 * np.pi * t) + 2
pl.plot(t, s)

pl.xlabel(r'time $\lambda$')
pl.ylabel(r'\textit{voltage (mV)}', fontsize=16)
pl.title(r'\TeX\ Number 1234567890 anisotropic ' +
         r'$\displaystyle\sum_{n=1}^\infty' +
         r'\frac{-e^{i\pi}}{2^n}$' +
         r' and \SI{3}{\micro\metre}', fontsize=16, color='r')

pl.grid(True)
pl.savefig('matplotlib_helvetica.pdf')