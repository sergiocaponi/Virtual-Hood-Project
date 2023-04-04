import time

class DPT:
    def __init__(self,addr,smbus):
        self.bus = smbus
        self.address = addr

        try:
            time.sleep(0.1)
            self.bus.write_i2c_block_data(self.address, 0x3F, [0xF9]) #Stop any cont measurement of the sensor
            time.sleep(0.8)
            self.bus.write_i2c_block_data(self.address, 0x36, [0X03])
        except Exception as error:
            print("CRITICAL: Failed to initialize pressure transducer;")
            print(error)

    def read(self):
        try:
            reading = self.bus.read_i2c_block_data(self.address,0,9)
        except Exception as error:
            print("ERROR: Failed to read pressure data;")
            print(error)
            return -99
        
        pressure_value=reading[0]+float(reading[1])/255
        if pressure_value>=0 and pressure_value<128:
            differential_pressure=pressure_value*240/256 #scale factor adjustment
        elif pressure_value>128 and pressure_value<=256:
            differential_pressure=-(256-pressure_value)*240/256 #scale factor adjustment
        elif pressure_value==128:
            differential_pressure=128 #Out of range
        
        return round(differential_pressure,4)