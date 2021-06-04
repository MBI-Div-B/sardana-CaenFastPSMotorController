import socket, time

from sardana import State
from sardana.pool.controller import MotorController
from sardana.pool.controller import Type, Description, DefaultValue


class CaenFastPSMotorController(MotorController):
    ctrl_properties = {'ip': {Type: str, Description: 'ip or hostname', DefaultValue: 'caen-fastps.hhg.lab'},
                       'port': {Type: int, Description: 'port', DefaultValue: 10001},
                       }
    
    MaxDevice = 1
    
    def __init__(self, inst, props, *args, **kwargs):
        super(CaenFastPSMotorController, self).__init__(
            inst, props, *args, **kwargs)

        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 
                                 socket.IPPROTO_TCP)
        self.conn.connect((self.ip, self.port))
        self.conn.settimeout(5)
        self.conn.setblocking(True)
        print('CAEN FAST-PS Initialization ... '),
        [_, idn] = self.__sendAndReceive('VER')
        if idn:
            print ('SUCCESS for model: %s' % idn)
        else:
            print ('FAILED!')
        # initialize hardware communication        
        self._motors = {}
        self._isMoving = False
        self._moveStartTime = None
        self._threshold = 0.0001
        self._target = None
        self._timeout = 10
        
    def AddDevice(self, axis):
        self._motors[axis] = True
        self.__sendAndReceive('UPMODE:NORMAL')
        self.__sendAndReceive('LOOP:I')
        self.__sendAndReceive('MON')

    def DeleteDevice(self, axis):
        del self._motors[axis]

    def StateOne(self, axis):
        limit_switches = MotorController.NoLimitSwitch
        pos = self.ReadOne(axis)
        now = time.time()
        
        try:
            if self._isMoving == False:
                state = State.On
            elif self._isMoving & (abs(pos-self._target) > self._threshold): 
                # moving and not in threshold window
                if (now-self._moveStartTime) < self._timeout:
                    # before timeout
                    state = State.Moving
                else:
                    # after timeout
                    self._log.warning('CAEN FAST-PS Timeout')
                    self._isMoving = False
                    state = State.On
            elif self._isMoving & (abs(pos-self._target) <= self._threshold): 
                # moving and within threshold window
                self._isMoving = False
                state = State.On
                #print('Kepco Tagret: %f Kepco Current Pos: %f' % (self._target, pos))
            else:
                state = State.Fault
        except:
            state = State.Fault
        
        return state, 'some text', limit_switches

    def ReadOne(self, axis):
        [_, pos] = self.__sendAndReceive('MRI')
        return float(pos)

    def StartOne(self, axis, position):
        self._moveStartTime = time.time()
        self._isMoving = True
        self._target = position
        cmd = 'MWI:%f' % position
        self.__sendAndReceive(cmd)

    def StopOne(self, axis):
        pass

    def AbortOne(self, axis):
        pass
    
    def SendToCtrl(self, cmd):
        """
        Send custom native commands. The cmd is a space separated string
        containing the command information. Parsing this string one gets
        the command name and the following are the arguments for the given
        command i.e.command_name, [arg1, arg2...]
        :param cmd: string
        :return: string (MANDATORY to avoid OMNI ORB exception)
        """
        # Get the process to send
        mode = cmd.split(' ')[0].lower()
        #args = cmd.strip().split(' ')[1:]

        if mode == 'moff':
            self.__sendAndReceive('MOFF')
            return ''
        elif mode == 'mon':
            self.__sendAndReceive('MON')
            return ''
        else:
            self._log.warning('Invalid command')
            return 'ERROR: Invalid command requested.'

    def __sendAndReceive(self, command):
        try:
            cmd = command+'\r'
            self.conn.send(cmd.encode("utf-8"))
            ret = self.conn.recv(1024).decode("utf-8")
            while (ret.find('\r\n') == -1):
                ret += self.conn.recv(1024).decode("utf-8")
        except socket.timeout:
            return [-2, '']
        except socket.error:
            print ('Socket error')
            return [-2, '']
        
        for i in range(len(ret)):
            if (ret[i] == ':'):
                return [str(ret[0:i]), ret[i+1:-2]]
        else:
            return [ret[:-2], '']  
