import sys, glob, time
import serial
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from IPython import display

def serial_ports():
    '''Функция определения номера порта'''
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # исключает текущий терминал "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Неподдерживаемая платформа.')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


def current_voltage(ser):
    '''Определение текущего напряжения смещения offset и амплитуды напряжения level'''
    byte_string = ser.read(22)
    if (byte_string[0] == int.from_bytes(b'\xaa', byteorder='little')) & (byte_string[-1] == sum(byte_string[:-1])%256):
        offset = int.from_bytes(byte_string[1:3], byteorder='little')/100
        level = byte_string[3]/100
        return {'offset':offset,
                'level':level}
    else:
        print('Прибор не обнаружен.')

        
def initialization(ser, f_start):
    byte_string = ser.read(22)
    if (byte_string[0] == int.from_bytes(b'\xaa', byteorder='little')) & (byte_string[-1] == sum(byte_string[:-1])%256):
        # установка начальной частоты
        ser.write(b'\x0d')
        frequency = int.from_bytes(byte_string[4:6], byteorder='little')*10**byte_string[6]
        while frequency != f_start:
            ser.write(b'\x01')
            byte_string = ser.read(22)
            frequency = int.from_bytes(byte_string[4:6], byteorder='little')*10**byte_string[6]

        # установка режима измерений
        if byte_string[10] != int.from_bytes(b'\x0c', byteorder='little'):
            ser.write(b'\x02')
    else:
        print('Прибор не обнаружен.')


def current_state(ser, byte_string):
    '''Сокращенный протокол работы с прибором, ограниченный определением Z и phi'''
    if (byte_string[0] == int.from_bytes(b'\xaa', byteorder='little')) & (byte_string[-1] == sum(byte_string[:-1])%256):
        frequency = int.from_bytes(byte_string[4:6], byteorder='little')*10**byte_string[6]
        Z = int.from_bytes(byte_string[16:19], byteorder='little')
        Z_order = byte_string[19]
        Z *= 10**(Z_order if (Z_order < 128) else Z_order - 256)
        phi = int.from_bytes(byte_string[12:15], byteorder='little', signed=True)
        phi_order = byte_string[15]
        phi *= 10**(phi_order if (phi_order < 128) else phi_order - 256)
        return {'frequency':frequency,
                'Z': Z,
                'phi': phi,
                'ReZ': Z*np.cos(np.pi*phi/180),
                'ImZ': Z*np.sin(np.pi*phi/180)}
    else:
        print('Прибор не обнаружен.')


def point_measurement(ser, columns, loops):
    '''Измерения в одной точке loops раз'''
    df_local = pd.DataFrame(columns=columns)
    for i in range(loops):
        state = current_state(ser, byte_string=ser.read(22))
        df_local = df_local.append(state, ignore_index=True)
    return df_local.median(axis=0)   # медианное усреднение


def frequencies(points, f_start, f_end):
    '''Рассчитывает частоты на которых должны быть произведены измерения'''
    points_we_need = points
    points_func = points
    while True:
        frequencies = np.geomspace(f_start, f_end, points_func)
        # разделяем массив частот на два, соответствующих единицам кГц и единицам Гц
        kHz_frequencies = np.array(np.round(frequencies[frequencies >= 1000]/1000), dtype=int)
        Hz_frequencies = np.array(np.round(frequencies[frequencies < 1000]), dtype=int)

        # оставляем только уникальные значения
        kHz_frequencies = np.unique(kHz_frequencies)[::-1]   
        Hz_frequencies = np.unique(Hz_frequencies)[::-1]
        
        frqs = np.concatenate((kHz_frequencies*1000, Hz_frequencies))
        # из-за округления число точек получается меньше желаемого -
        # повторяем процедуру до схождения
        if len(frqs) < points_we_need:
            points_func += 1
        else:
            return frqs

        
def live_plot(df):
    '''Построение графика по текущему набору данных с регулярным обновлением'''
    plt.figure(figsize=(10, 5))
    plt.plot(df['ReZ'], -df['ImZ'], 'o', color='blue')
    plt.xlabel("$Z'$, Ом")
    plt.ylabel("$Z''$, Ом")
    plt.axis('equal')
    display.clear_output(wait=True)
    display.display(plt.gcf())
    plt.gcf().show()


def spectra_measurement(f_start = 10**6, f_end = 25, points=17, loops=10, path='ZZ.csv'):
    '''Полное измерение спектра: грубое или поточечное'''
    port = serial_ports()[0]  #! сделать проверку порта
    columns =['frequency', 'Z', 'phi', 'ReZ', 'ImZ']
    df = pd.DataFrame(columns = columns)
    with serial.Serial(port, 9600, timeout=2) as ser:
        initialization(ser, f_start)
        live_plot(df)
        if points <= 17:              # режим грубых измерений
            while (df['frequency'].iloc[-1] != f_end):
                local_df = point_measurement(ser, columns, loops)
                df = df.append(local_df, ignore_index=True)
                live_plot(df)
                ser.write(b'\x09')    # аналогично нажатию клавиши "влево"
        else:                         # режим точных измерений
            frqs = frequencies(points, f_start, f_end)
            for f in frqs:
                while True:
                    byte_string = ser.read(22)
                    real_frequency = int.from_bytes(byte_string[4:6], byteorder='little')*10**byte_string[6]
                    if real_frequency == f:
                        local_df = point_measurement(ser, columns, loops)
                        df = df.append(local_df, ignore_index=True)
                        live_plot(df)
                        ser.write(b'\x04') # аналогично нажатию клавиши "вниз"
                        break
                    else:
                        ser.write(b'\x04') # аналогично нажатию клавиши "вниз"  
        ser.close()
    return df