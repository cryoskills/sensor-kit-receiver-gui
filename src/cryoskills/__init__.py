## Main Imports
import argparse
import datetime
from dataclasses import dataclass
import numpy as np
import pathlib 
import serial
import struct
import time
import threading

## TK Imports
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)


@dataclass
class CryoSkillsPacket:
    
    rssi : int
    packet_type : int
    packet_length : int         
    packet_id : int             
    sensor_id : int
    ds18b20_temperature : float
    pt1000_temperature : float
    raw_adc_value : int
    battery_voltage : float
    battery_current : float
    solar_panel_voltage : float
    solar_panel_current : float
    load_voltage : float
    load_current : float
    receiver_timestamp : datetime.datetime
    transmitter_timestamp: datetime.datetime
    pc_timestamp : datetime.datetime

    @staticmethod
    def from_serial(serial_data):
        
        # return packet object
        return CryoSkillsPacket(

            ## #################################################
            # No need to convert the int, defaults to the correct type
            rssi = int.from_bytes(serial_data[0:0+4], byteorder='little', signed=True),
            # Receive timestamp:
                # read in 20 chars,
                # convert to a string,
                # convert to a datetime
            receiver_timestamp = CryoSkillsPacket.convert_datetime(
                serial_data[4:4+20].decode("utf8")
            ),
            # BEGIN cryo_radio_packet
            packet_type = serial_data[24],
            packet_length = serial_data[25],
            #
            packet_id = int.from_bytes(serial_data[28:28+4], byteorder='little', signed=False),
            #
            sensor_id = int.from_bytes(serial_data[32:32+4], byteorder='little', signed=False),
            # 
            # Temperature values
            ds18b20_temperature = struct.unpack('<f', serial_data[36:36+4]),
            pt1000_temperature = struct.unpack('<f', serial_data[40:40+4]),
            #
            raw_adc_value = int.from_bytes(serial_data[44:44+4], byteorder='little', signed=False),
            #
            battery_voltage = struct.unpack('<f', serial_data[48:48+4]),
            battery_current = struct.unpack('<f', serial_data[52:52+4]),
            solar_panel_voltage = struct.unpack('<f', serial_data[56:56+4]),
            solar_panel_current = struct.unpack('<f', serial_data[60:60+4]),
            load_voltage = struct.unpack('<f', serial_data[64:64+4]),
            load_current = struct.unpack('<f', serial_data[68:68+4]),
            #
            transmitter_timestamp = CryoSkillsPacket.convert_datetime(
                serial_data[72:72+20].decode("utf8")
            ),
            #
            pc_timestamp = datetime.datetime.now()

        )
    
    @staticmethod
    def convert_datetime(datetime_string):
        if datetime_string[-1] == '\x00':
            return datetime.datetime.strptime(datetime_string[0:-1], "%d-%m-%Y %H:%M:%S")
        else:
            return datetime.datetime.strptime(datetime_string, "%d %b %Y %H:%M:%S")
        
class CryoSkillsLogger:

    MAX_PACKETS_PER_SENSOR = 256
    DELETE_PACKETS_AFTER = 60 * 60 # 1 hour in seconds

    def __init__(self, filename):
        # open the file regardless
        self.filename = pathlib.Path(filename)
        # Check whether file exists
        file_exists = self.filename.exists()
        # then write the header if it didn't exist
        if not file_exists:
            self.write_header()
        # initialise local memory for packets
        self.buffer = dict()

    def __del__(self):
        # Close file
        pass

    def __get_packet_headers(self): 
        return list(CryoSkillsPacket.__dataclass_fields__.keys())

    def write_header(self):
        with open(self.filename, "a+") as fh:
            # collect headers
            headers = self.__get_packet_headers()
            # write line with comma separation
            fh.write(
                ",".join(headers)
            )
            fh.write("\n")

    def write_packet(self, packet): 
        with open(self.filename, "a+") as fh:
            # collate packet fields
            headers = self.__get_packet_headers()
            # sort fields by header
            fields = []
            for header in headers: 
                # and conver to string - a bit sloppy!
                # TODO: do better here...
                field = packet.__getattribute__(header)
                if isinstance(field, tuple):
                    field = field[0]
                fields.append(str(field))
            # write line to file
            fh.write(
                ",".join(fields)
            )
            fh.write("\n\r")
            print(",".join(fields))

        # Check if we have a buffer to append to already
        if not packet.sensor_id in self.buffer.keys():
            self.buffer[packet.sensor_id] = list()
        # otherwise, 
        else:
            # for FIFO stack, pop 0 if we exceed the max size
            if len(self.buffer[packet.sensor_id]) >=  CryoSkillsLogger.MAX_PACKETS_PER_SENSOR:
                self.buffer[packet.sensor_id].pop(0)
        # and append in either case
        self.buffer[packet.sensor_id].append(packet)

    def garbage_collect_packets(self):
        
        # Get current time
        now = datetime.datetime.now()

        # Iterate over all sensors
        for sensor_id in self.buffer:
            # and all packets
            for packet in self.buffer[sensor_id]:
                if (now - packet.pc_timestamp) > CryoSkillsLogger.DELETE_PACKETS_AFTER:
                    print(f"Deleting packet {packet.packet_id}")
                    self.buffer[sensor_id].delete(packet)

    def get_unique_sensor_ids(self):
        return self.buffer.keys() 

class CryoSkillsLoggerApp(tk.Tk, threading.Thread):

    SERIAL_RECONNECT_ATTEMPS = 5 # maximum attempts
    SERIAL_RECONNECT_DELAY = 5 # second

    def __init__(self, serial_port, baud_rate, filename, gui=False, *args, **kwargs):

        self._gui_enabled = gui
        # Initialise GUI if selected
        if gui:
            self.__init__gui__(*args, **kwargs)
            self.protocol("WM_DELETE_WINDOW", self.kill)

        # Initialise thread
        threading.Thread.__init__(self)

        # Store logging variables
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.filename = filename

        # Create logger object
        self.logger = CryoSkillsLogger(filename)
        self.selectedData = 'All'

        # Initialise reconnect counts
        self.serial_reconnects = 0

        # Begin thread
        self.alive = False
        self.start()

    def run(self):

        # main logging thread
        self.alive = True

        # open serial port
        while self.serial_reconnects < CryoSkillsLoggerApp.SERIAL_RECONNECT_ATTEMPS:

            try:
    
                # make serial port connection
                rx_port = serial.Serial(self.serial_port, baudrate=self.baud_rate, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=None)
            
                # keep receiving
                while self.alive:
                    self.receive(rx_port)
    
            except serial.SerialException:
                self.serial_reconnects -= 1
                time.sleep(CryoSkillsLoggerApp.SERIAL_RECONNECT_DELAY)

            except KeyboardInterrupt:
                print(f"Closing log and releasing {self.serial_port}")
                rx_port.close()
                self.kill()    

    def receive(self, rx_port):

        if self._gui_enabled:
            self.update_gui()

        # throw away any incident bytes until we see the magic word 0xc5c5
        magic_word = [-1, -1];
        try:
            while not (magic_word[0] == 0xc5 and magic_word[1] == 0xc5):
                magic_word[0] = magic_word[1]
                magic_word[1] = int.from_bytes(rx_port.read(size = 1))
                # print(f"Waiting for magic word: {magic_word[0]}, {magic_word[1]}")
        except KeyboardInterrupt:
            print("Quitting")
            return
        
        # print(f"Magic word {magic_word[0]}, {magic_word[1]}")

        # Get packet length
        packet_length = rx_port.read(size = 2)

        # Deal with comment
        ##  TODO: check what packet length this would equate to, will be >> 255...
        if packet_length.decode("utf8") == "# ":
            print(rx_port.readline())
            return
        else: 
            
            # we have a packet to decode
            packet_length = int.from_bytes(
                packet_length, 
                byteorder = 'little', 
                signed=False
            )

            # read packet
            packet_raw = rx_port.read(size = packet_length - 4)

            # covert to packet object
            packet_obj = CryoSkillsPacket.from_serial(packet_raw)

            # store in the logger for the correct channel
            self.logger.write_packet(packet_obj)
            # print(f"{packet_obj.sensor_id:x}: {packet_obj.packet_id}")
        
            # Update the sensor list
            self.sensorListUpdate()

    def kill(self):
        self.alive = False
        self.destroy()

    def __init__gui__(self, *args, **kwargs):

        # Initialise TK window
        super().__init__(*args, **kwargs)

        # TODO: setup GUI components
        self.title("CryoSkills Receiver")
        self.geometry("1200x800")

        # Create a plotting figure
        self.dataFigure = Figure()
        self.dataFigure.subplots_adjust(
            left = 0.05,
            bottom = 0.05,
            right = 0.95,
            top = 0.95,
            wspace = 0.4,
            hspace = 0.4
        )

        self.digitalAx = self.dataFigure.add_subplot(221)
        self.analogueAx = self.dataFigure.add_subplot(222)
        self.rssiAx = self.dataFigure.add_subplot(223)
        self.solarAx = self.dataFigure.add_subplot(224)

        self.dataFigureCanvas = FigureCanvasTkAgg(self.dataFigure, master=self)
        self.dataFigureCanvas.draw()
        self.dataFigureCanvas.get_tk_widget().grid(padx=8, pady=8, row=0, column=1, sticky=(tk.E + tk.N + tk.W + tk.S))
        # Set data figure weight to 1
        self.columnconfigure(1, weight=1)
        # self.columnconfigure(0, weight=0)
        self.rowconfigure(0, weight=1)

        self.sensorList = tk.Listbox()
        self.sensorList.grid(padx=8, pady=8, row=0, column=0,  sticky=(tk.E + tk.N + tk.W + tk.S))
        self.sensorList.bind("<<ListboxSelect>>", lambda evt : self.sensorListSelect(evt))

    def sensorListUpdate(self):
        # Delete all the times    
        self.sensorList.delete(0, self.sensorList.size())
        # Iterate through datastore and assign sensor IDs
        count = 0
        self.sensorList.insert(count, 'All')
        count += 1
        for id in self.logger.get_unique_sensor_ids():
            self.sensorList.insert(count, f"{id:x}")
            count += 1
        pass

    def sensorListSelect(self, evt):
        # Note here that Tkinter passes an event object to onselect()
        w = evt.widget
        index = int(w.curselection()[0])
        value = w.get(index)
        self.selectedData = value
        
    def update_gui(self):
        
        # Clear axes
        self.digitalAx.clear()
        self.analogueAx.clear()
        self.solarAx.clear()
        self.rssiAx.clear()

        # Add labels
        self.digitalAx.set_title("Digital")
        self.digitalAx.set_ylabel('C')
        self.analogueAx.set_title("Analogue")
        self.analogueAx.set_ylabel('C')
        self.solarAx.set_title("Solar Power")
        self.solarAx.set_ylabel('W')
        self.rssiAx.set_title("Signal Strength")
        self.rssiAx.set_ylabel("dBm")

        # Plot
        for sensor_id, packets in self.logger.buffer.items():

            if self.selectedData == 'All' or self.selectedData == f"{sensor_id:x}":
                # timestamp 
                timestamp = []
                digitalTemp = []
                analogueTemp = []
                rssi = []
                solarPower = []
                for packet in packets:
                    timestamp.append(packet.pc_timestamp)
                    digitalTemp.append(packet.ds18b20_temperature)
                    analogueTemp.append(packet.pt1000_temperature)
                    rssi.append(packet.rssi)
                    solarPower.append(packet.solar_panel_voltage[0]*packet.solar_panel_current[0])

                self.digitalAx.plot(timestamp, digitalTemp, '.')
                self.analogueAx.plot(timestamp, analogueTemp, '.')
                self.rssiAx.plot(timestamp, rssi, '.')
                self.solarAx.plot(timestamp, solarPower, '.')
                # self.analogueAx.plot(datastore.timestamp, datastore.temperature, '.')
                # self.solarAx.plot(datastore.timestamp, datastore.pressure, '.')
                # self.rssiAx.plot(datastore.timestamp, datastore.rssi, '.')

        self.dataFigureCanvas.draw()

        self.update()

def parse_cmd_arguments():
    
    # Create instance of command line argument parser
    parser = argparse.ArgumentParser(
        prog="CryoSkills Receiver",
        description='Log and graphically display CryoSkills LoRa radio packets from CryoSkills dataloggers.'
    )

    parser.add_argument(
        '--port', type=str, required=False, 
        default="COM12",
        help="serial port of receiver Adalogger (i.e. COM12)"
    )

    parser.add_argument(
        '--baud', type=int, required=False, 
        default=9600,
        help="baud rate of serial port (i.e. 9600, 115200) - must match receiver Adalogger!"
    )

    # Create default log filename with current datetime stamp
    # TODO: probably better to move this logic elsewhere, but this will do for now
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    parser.add_argument(
        '--filename', type=str, required=False, 
        default=f"cryoskills_log_{timestamp}.csv",
        help="filename to write decoded packets to, defaults to a timestamped CSV file."
    )

    # Return arguments
    return parser.parse_args()

def launch_gui_instance():

    # Parse command line arguments
    args = parse_cmd_arguments()

    # Print actions
    print(f"Opening serial communication on port {args.port} @ {args.baud}")
    print(f"Log file output to {args.filename}")

    app = CryoSkillsLoggerApp(args.port, args.baud, args.filename, gui=True)
    app.mainloop()


if __name__ == "__main__":
    launch_gui_instance()