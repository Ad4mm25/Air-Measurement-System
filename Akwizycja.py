#!/usr/bin/env python
#  -*- coding: utf-8 -*-


from __future__ import print_function
from time import sleep
from sys import stdout
from daqhats import mcc128, OptionFlags, HatIDs, HatError, AnalogInputMode, \
    AnalogInputRange
from daqhats_utils import select_hat_device, enum_mask_to_string, \
    input_mode_to_string, input_range_to_string
from csv_logger import CsvLogger
import logging
from datetime import datetime
import RPi.GPIO as GPIO
import os

# Constants
CURSOR_BACK_2 = '\x1b[2D'
ERASE_TO_END_OF_LINE = '\x1b[0K'

SLOW_SAMPLING = 0.2
FAST_SAMPLING = 0.01

        

def main():
    """
    This function is executed automatically when the module is run directly.
    """
    sleep(14)

    GPIO.setmode(GPIO.BCM)
    ###############################################################################
    #LEDY
    GREEN_LED = 23
    YELLOW_LED = 24
    RED_LED = 25
    GPIO.setup(GREEN_LED, GPIO.OUT)
    GPIO.output(GREEN_LED, GPIO.HIGH)
    GPIO.setup(YELLOW_LED, GPIO.OUT)
    GPIO.output(YELLOW_LED, GPIO.LOW)
    GPIO.setup(RED_LED, GPIO.OUT)
    GPIO.output(RED_LED, GPIO.LOW)


    #PRZYCISKI
    BUTTON1 = 6
    BUTTON2 = 5
    GPIO.setup(BUTTON1, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    GPIO.setup(BUTTON2, GPIO.IN, pull_up_down = GPIO.PUD_UP)

    
    #USTAWIENIA POMIARU
    options = OptionFlags.DEFAULT
    low_chan = 0
    high_chan = 1
    input_mode = AnalogInputMode.SE
    input_range = AnalogInputRange.BIP_10V
    mcc_128_num_channels = mcc128.info().NUM_AI_CHANNELS[input_mode]
    sample_interval = SLOW_SAMPLING  # Seconds
    ###############################################################################



    ###############################################################################
    # GLOWNA PETLA
    repeatMeasurement = True
    while repeatMeasurement == True:      
        mode = 0
        buttonPressed = False


        # SPRAWDZENIE CZY JEST PENDRIVE
        if os.path.exists("/media/akwizycja/SZALENSTWO/Pomiary"):
            #WYBOR PROGRAMU
            while (buttonPressed == False):
                if not GPIO.input(BUTTON1):
                    sample_interval = SLOW_SAMPLING
                    buttonPressed = True
                    mode = 0
                elif not GPIO.input(BUTTON2):
                    sample_interval = FAST_SAMPLING
                    buttonPressed = True
                    mode = 1
            
            sleep(0.5)
            buttonPressed = False

            # UTWORZENIE PLIKU CSV
            if mode == 0:
                filename = '/media/akwizycja/SZALENSTWO/Pomiary/Pomiar'+str(datetime.now().strftime('%m%d-%H%M%S'))+'_SLOW.csv'
            else:
                filename = '/media/akwizycja/SZALENSTWO/Pomiary/Pomiar'+str(datetime.now().strftime('%m%d-%H%M%S'))+'_FAST.csv'

            print(filename)
            delimiter = ','
            level = logging.INFO
            fmt = f'%(asctime)s{delimiter}%(relativeCreated)d{delimiter}%(message)s'
            datefmt = '%H:%M:%S'
            max_size = 3758096384  # 3.5 gigabytes
            max_files = 6  # 6 rotating files
            header = ['Godzina', 'Milisekundy', 'Nr', 'Cisnienie [bar]', 'Natezenie [l/min]']

            # Create logger with csv rotating handler
            csvlogger = CsvLogger(filename=filename,
                              delimiter=delimiter,
                              level=level,
                              fmt=fmt,
                              datefmt=datefmt,
                              max_size=max_size,
                              max_files=max_files,
                              header=header)

            

            # INICJALIZACJA DAQHAT
            try:
                # Ensure low_chan and high_chan are valid.
                if low_chan < 0 or low_chan >= mcc_128_num_channels:
                    error_message = ('Error: Invalid low_chan selection - must be '
                                     '0 - {0:d}'.format(mcc_128_num_channels - 1))
                    raise Exception(error_message)
                if high_chan < 0 or high_chan >= mcc_128_num_channels:
                    error_message = ('Error: Invalid high_chan selection - must be '
                                     '0 - {0:d}'.format(mcc_128_num_channels - 1))
                    raise Exception(error_message)
                if low_chan > high_chan:
                    error_message = ('Error: Invalid channels - high_chan must be '
                                     'greater than or equal to low_chan')
                    raise Exception(error_message)

                # Get an instance of the selected hat device object.
                address = select_hat_device(HatIDs.MCC_128)
                hat = mcc128(address)

                hat.a_in_mode_write(input_mode)
                hat.a_in_range_write(input_range)



                
                # URUCHOMIENIE TRYBU, ZAPALENIE LED
                if mode == 0:
                    GPIO.output(YELLOW_LED, GPIO.HIGH)
                else:
                    GPIO.output(RED_LED, GPIO.HIGH)



                # PRACA
                working = True
                try:
                    samples_per_channel = 0
                    tick = 0
                    while (working == True):
                        # Display the updated samples per channel count
                        samples_per_channel += 1


                        # ODCZYT DANYCH Z DAQHAT
                        valueP = hat.a_in_read(low_chan, options)
                        valueQ = 100 * hat.a_in_read(high_chan, options)


                        # ZAPIS DO PLIKU
                        csvlogger.info(str(samples_per_channel)+','+f'{valueP:.5f}'+','+f'{valueQ:.3f}')
                        stdout.flush()


                        # ZAKONCZENIE POMIARU
                        if ((not GPIO.input(BUTTON1)) or (not GPIO.input(BUTTON2))):
                            if mode == 0:
                                tick = tick+20
                            else:
                                tick = tick+1
                        else:
                            tick = 0

                        if tick > 100:
                            working = False

                        # Wait the specified interval between reads.
                        sleep(sample_interval)


                except KeyboardInterrupt:
                    # Clear the '^C' from the display.
                    print(CURSOR_BACK_2, ERASE_TO_END_OF_LINE, '\n')


                # Zgaszenie LED
                GPIO.output(YELLOW_LED, GPIO.LOW)
                GPIO.output(RED_LED, GPIO.LOW)
                sleep(1)
                
                buttonPressed = False
                tickLED = 0
                tick1 = 0
                tick2 = 0


                # OCZEKIWANIE NA DECYZJE OPERATORA
                while (buttonPressed == False):
                    tickLED += 1
                    if not GPIO.input(BUTTON1):         #POWTORZ POMIAR
                        tick1 += 1
                        if tick1 > 5:
                            buttonPressed = True
                            repeatMeasurement = True
                    elif not GPIO.input(BUTTON2):       #ZAMKNIJ PROGRAM
                        tick2 += 1
                        if tick2 > 5:
                            buttonPressed = True
                            repeatMeasurement = False
                    else:
                        tick1 = 0
                        tick2 = 0

                    #miganie diody
                    if tickLED == 4:
                        GPIO.output(GREEN_LED, GPIO.LOW)
                    elif tickLED == 8:
                        GPIO.output(GREEN_LED, GPIO.HIGH)
                        tickLED = 0
                        
                    sleep(0.1)

                GPIO.output(GREEN_LED, GPIO.LOW)
                sleep(3)    
                GPIO.output(GREEN_LED, GPIO.HIGH)

                
            # BLAD DAQHAT
            except (HatError, ValueError) as error:
                print("Daqhat Error")
                try:
                    tickLED = 0
                    tick1 = 0
                    tick2 = 0
                    
                    # OCZEKIWANIE NA DECYZJE OPERATORA
                    while (buttonPressed == False):
                        tickLED += 1
                        if not GPIO.input(BUTTON1):         #POWTORZ POMIAR
                            tick1 += 1
                            if tick1 > 10:
                                buttonPressed = True
                                repeatMeasurement = True
                        elif not GPIO.input(BUTTON2):       #ZAMKNIJ PROGRAM
                            tick2 += 1
                            if tick2 > 10:
                                buttonPressed = True
                                repeatMeasurement = False
                        else:
                            tick1 = 0
                            tick2 = 0

                        #miganie diod
                        if tickLED == 4:
                            GPIO.output(GREEN_LED, GPIO.LOW)
                            GPIO.output(YELLOW_LED, GPIO.LOW)
                            GPIO.output(RED_LED, GPIO.LOW)
                        elif tickLED == 8:
                            GPIO.output(GREEN_LED, GPIO.HIGH)
                            GPIO.output(YELLOW_LED, GPIO.HIGH)
                            GPIO.output(RED_LED, GPIO.HIGH)
                            tickLED = 0
                                
                        sleep(0.1)

                    GPIO.output(GREEN_LED, GPIO.LOW)
                    GPIO.output(YELLOW_LED, GPIO.LOW)
                    GPIO.output(GREEN_LED, GPIO.LOW)
                    sleep(3)    
                    GPIO.output(GREEN_LED, GPIO.HIGH)

                except KeyboardInterrupt:
                    print(CURSOR_BACK_2, ERASE_TO_END_OF_LINE, '\n')
                    GPIO.output(YELLOW_LED, GPIO.LOW)
                    GPIO.output(RED_LED, GPIO.LOW)
                    GPIO.output(GREEN_LED, GPIO.LOW)
                    repeatMeasurement = False
                    sleep(4)    
                    GPIO.output(GREEN_LED, GPIO.HIGH)


        # BRAK DYSKU USB       
        else:
            print("No pendrive")
            try:
                tickLED = 0
                tick1 = 0
                tick2 = 0
                GPIO.output(GREEN_LED, GPIO.HIGH)
                    
                # OCZEKIWANIE NA DECYZJE OPERATORA
                while (buttonPressed == False):
                    tickLED += 1
                    if not GPIO.input(BUTTON1):         #POWTORZ POMIAR
                        tick1 += 1
                        if tick1 > 10:
                            buttonPressed = True
                            repeatMeasurement = True
                    elif not GPIO.input(BUTTON2):       #ZAMKNIJ PROGRAM
                        tick2 += 1
                        if tick2 > 10:
                            buttonPressed = True
                            repeatMeasurement = False
                    else:
                        tick1 = 0
                        tick2 = 0

                    #miganie diod
                    if tickLED == 4:
                        GPIO.output(YELLOW_LED, GPIO.LOW)
                        GPIO.output(RED_LED, GPIO.LOW)
                    elif tickLED == 8:
                        GPIO.output(YELLOW_LED, GPIO.HIGH)
                        GPIO.output(RED_LED, GPIO.HIGH)
                        tickLED = 0
                            
                    sleep(0.1)

                GPIO.output(RED_LED, GPIO.LOW)
                GPIO.output(YELLOW_LED, GPIO.LOW)
                GPIO.output(GREEN_LED, GPIO.LOW)
                sleep(4)    
                GPIO.output(GREEN_LED, GPIO.HIGH)

            except KeyboardInterrupt:
                print(CURSOR_BACK_2, ERASE_TO_END_OF_LINE, '\n')
                GPIO.output(YELLOW_LED, GPIO.LOW)
                GPIO.output(RED_LED, GPIO.LOW)
                GPIO.output(GREEN_LED, GPIO.LOW)
                repeatMeasurement = False
                sleep(4)    
                GPIO.output(GREEN_LED, GPIO.HIGH)
                
        


if __name__ == '__main__':
    # This will only be run when the module is called directly.
    main()
    print("closing")
    GPIO.cleanup()
    sleep(1)
    os.system("sudo shutdown -h now")
