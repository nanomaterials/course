import numpy as np
import matplotlib.pyplot as plt

indices = {'air': '1*x/x',
           'SiO2': 'np.sqrt(1+0.6961663/(1-np.power(0.0684043/x, 2))+0.4079426/(1-np.power(0.116241/x,2))+0.8974794/(1-np.power(9.896161/x,2)))',
           'TiO2': 'np.sqrt(5.913+0.2441/(np.power(x, 2)-0.0803))'}

def n(material, x):
    nL = lambda x: eval(indices[material])
    return nL(x)


def dot_product(M, B):
    return np.array([[M[0,0,:]*B[0,0,:]+M[0,1,:]*B[1,0,:],
                   M[0,0,:]*B[0,1,:]+M[0,1,:]*B[1,1,:]],
                  [M[1,0,:]*B[0,0,:]+M[1,1,:]*B[1,0,:],
                   M[1,0,:]*B[0,1,:]+M[1,1,:]*B[1,1,:]]])


def A(wavelengths, material_1, material_2):
    n1 = n(material_1, wavelengths)
    n2 = n(material_2, wavelengths)
    return [[n2+n1, n2-n1],
            [n2-n1, n2+n1]]/(2*n2)


def B(wavelengths, material, L):
    nm = n(material, wavelengths)
    return np.array([[np.exp(2*np.pi*1j*nm*L/wavelengths),
                      np.zeros(nm.size)],
                     [np.zeros(nm.size),
                      np.exp(-2*np.pi*1j*nm*L/wavelengths)]])


def M(structure, wavelengths):
    materials = structure[0::2]
    thicknesses = np.array(structure[1::2])/1000
    matrix_M = A(wavelengths, materials[0], materials[1])
    for i in range(len(materials)-2):
        matrix_B = B(wavelengths, materials[i+1], thicknesses[i+1])
        matrix_M = dot_product(matrix_M, matrix_B)
        matrix_A = A(wavelengths, materials[i+1], materials[i+2])
        matrix_M = dot_product(matrix_M, matrix_A)
    return matrix_M


def T(structure, xmin=300, xmax=1000):
    wavelengths = np.linspace(xmin/1000, xmax/1000, num=1000)
    M_matrix = M(structure, wavelengths)
    T = 1 - np.abs(-M_matrix[1, 0]/M_matrix[1, 1])**2
    plt.xlabel(r'$\lambda$, нм')
    plt.ylabel(r'$T$, %')
    #plt.xticks([400, 600, 800, 1000])
    #plt.yticks([0, 25, 50, 75, 100])
    plt.axis([xmin, xmax, 0, 100])
    plt.plot(wavelengths*1000, T*100, color='blue')
    plt.tight_layout()