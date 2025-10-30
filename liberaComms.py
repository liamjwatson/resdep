from typing import Union
import pexpect
import sys
import os
from shutil import ExecError

class LiberaBLM:
    """
    A libera object which stores ssh and config parameters, and handles commonly used commands.
    Only works on Unix based systems due to the use of bash commands.
    """
    def __init__(self, ):
        # ssh params
        self._user      : str = "root"
        self._host      : str = "SR11IOC91"
        self.__password : str = "Jungle"
        self._command   : str = ""

        # current values
        self.adc_offset_1: Union[int, None] = None
        self.adc_window_1: Union[int, None] = None
        self.adc_offset_2: Union[int, None] = None
        self.adc_window_2: Union[int, None] = None

        # init values
        self.init_adc_offset_1: Union[int, None] = None
        self.init_adc_window_1: Union[int, None] = None
        self.init_adc_offset_2: Union[int, None] = None
        self.init_adc_window_2: Union[int, None] = None

        # defaults
        self._default_adc_offset_1: int = 0
        self._default_adc_window_1: int = 16
        self._default_adc_offset_2: int = 0
        self._default_adc_window_2: int = 16

        # create log folder (if not running on remote OPI)
        self.__write_permissions: bool = True
        try:
            if not os.path.exists('libera_logs'):
                os.mkdir('libera_logs')
        except PermissionError:
            print("You dont have write permissions to save logfiles, logging to sys.stdout.")
            self.__write_permissions = False
            self._logfile=sys.stdout
    #
    # ----------------------------------------------------------------------------------------------------------
    def get_adc_windows(self, ) -> tuple[Union[int, None], ...]:
        """
        Queries current ADC window config
        """
        self._command   = "libera-ireg dump application.signal_processing.{adc_counter_mask1,adc_counter_mask2}"
        ssh_cmd         = f"ssh {self._user}@{self._host} '{self._command}'"

        if self.__write_permissions:
            self._logfile = open(os.path.join('libera_logs', 'get_adc_windows.log'), 'w')
            self._logfile.write(f">> {ssh_cmd}\n")

        # Run command over ssh
        try:
            # this should error if something goes wrong
            out: Union[str, tuple[str, int]] = pexpect.run(ssh_cmd, encoding='utf-8', timeout=10, logfile=self._logfile)
            
            if isinstance(out, str):
                # check if out is actually err msg
                if out[:4] in ['ireg', 'WARN', 'Erro']:
                    raise ExecError(f"Error from Libera BLM IOC:\n{out}")
                # format out
                fout: list[str] = out.strip().splitlines()
                for index, value in enumerate(out):
                    fout[index] = value.strip()
                self.adc_offset_1 = int(fout[1][7:])
                self.adc_window_1 = int(fout[2][7:])
                self.adc_offset_2 = int(fout[4][7:])
                self.adc_window_2 = int(fout[5][7:])

        finally:
            if self.__write_permissions:
                self._logfile.close()

        
        conditions = [
            self.adc_offset_1 is None,
            self.adc_window_1 is None,
            self.adc_offset_2 is None,
            self.adc_window_2 is None
        ]

        if any(conditions):
            raise ExecError("get_adc_windows returned 'None's.")

        return self.adc_offset_1, self.adc_window_1, self.adc_offset_2, self.adc_window_2
    #
    # ----------------------------------------------------------------------------------------------------------
    def put_adc_windows(self, adc_offset_1: int, adc_window_1: int, adc_offset_2: int, adc_window_2: int):
        """
        Alters ADC window config

        Parameters
        ----------
        adc_offset_1 : int (0-16)
            Offset for the first count window
        adc_window_1 : int (0-16)
            Size of the first count window
        adc_offset_2 : int (0-16)
            Second offset...
        adc_window_2 : int (0-16)
            Second window...

        Returns
        -------
        Updates all values self.adc_{offset | window}_{1 | 2}

        """

        # -- input error checking
        # values have to be 0--16
        # offset + mask <= 16
        conditions = [
            0 <= adc_offset_1 <= 16,
            0 <= adc_window_1 <= 16, 
            0 <= adc_offset_2 <= 16,
            0 <= adc_window_2 <= 16,
            adc_offset_1 + adc_window_1 <= 16,
            adc_offset_2 + adc_window_2 <= 16,
        ]
        if not all(conditions):
            raise ValueError("Each offset and window input must be an int between 0 and 16.")

        # Check if initial values have been read -- otherwise read
        conditions = [
            self.init_adc_offset_1 is None,
            self.init_adc_window_1 is None,
            self.init_adc_offset_2 is None,
            self.init_adc_window_2 is None
        ]
        if any(conditions):
            self.get_init_adc_windows()

        # init commands
        commands = [
            f'adc_counter_mask1.offset={adc_offset_1}',
            f'adc_counter_mask1.window={adc_window_1}',
            f'adc_counter_mask2.offset={adc_offset_2}',
            f'adc_counter_mask2.window={adc_window_2}'
        ]

        # Can only assign one new value at a time so loop
        for cmd in commands:

            self._command   = f"libera-ireg access application.signal_processing.{cmd}"
            ssh_cmd         = f"ssh {self._user}@{self._host} '{self._command}'"

            # Spawn the SSH process
            # this should error if something goes wrong
            out: Union[str, tuple[str, int]] = pexpect.run(ssh_cmd, encoding='utf-8', timeout=10)

            # Check for err msg
            if out[:4] in ['ireg', 'WARN', 'Erro'] and isinstance(out, str):
                raise ExecError(f"Error from Libera BLM IOC:\n{out}")

        # update values
        self.adc_offset_1 = adc_offset_1
        self.adc_window_1 = adc_window_1
        self.adc_offset_2 = adc_offset_2
        self.adc_window_2 = adc_window_2

    #
    # ----------------------------------------------------------------------------------------------------------
    def get_init_adc_windows(self, ):
        """
        Queries current ADC window config
        ** there is a hardcoded check for initial values in any functions that change values
        ** ideally run this at start before changing values
        """

        self._command   = "libera-ireg dump application.signal_processing.{adc_counter_mask1,adc_counter_mask2}"
        ssh_cmd         = f"ssh {self._user}@{self._host} '{self._command}'"

        if self.__write_permissions:
            self._logfile = open(os.path.join('libera_logs', 'get_init_adc_windows.log'), 'w')
            self._logfile.write(f">> {ssh_cmd}\n")

        # Spawn the SSH process
        try:
            out: Union[str, tuple[str, int]] = pexpect.run(ssh_cmd, encoding='utf-8', logfile=self._logfile)

            if isinstance(out, str):
                # Check out is not err msg
                if out[:4] in ['ireg', 'WARN', 'Erro']:
                    raise ExecError(f"Error from Libera BLM IOC:\n{out}")
                # format out
                fout: list[str] = out.strip().splitlines()
                for index, value in enumerate(out):
                    fout[index] = value.strip()
                self.init_adc_offset_1 = int(fout[1][7:])
                self.init_adc_window_1 = int(fout[2][7:])
                self.init_adc_offset_2 = int(fout[4][7:])
                self.init_adc_window_2 = int(fout[5][7:])

        finally:
            if self.__write_permissions:
                self._logfile.close()

        return self.init_adc_offset_1, self.init_adc_window_1, self.init_adc_offset_2, self.init_adc_window_2

    #
    # ----------------------------------------------------------------------------------------------------------
    def restore_init_adc_windows(self, ):
        """
        Restore initial values
        """

        # Check if initial values have been read 
        # -- otherwise error since you shouldn't have to restore what you haven't changed
        conditions = [
            self.init_adc_offset_1 is None,
            self.init_adc_window_1 is None,
            self.init_adc_offset_2 is None,
            self.init_adc_window_2 is None
        ]
        if any(conditions):
            raise ValueError("No stored inital values to reset.")

        # init commands
        commands = [
            f'adc_counter_mask1.offset={self.init_adc_offset_1}',
            f'adc_counter_mask1.window={self.init_adc_window_1}',
            f'adc_counter_mask2.offset={self.init_adc_offset_2}',
            f'adc_counter_mask2.window={self.init_adc_window_2}'
        ]

        # Can only assign one new value at a time so loop
        for cmd in commands:

            self._command   = f"libera-ireg access application.signal_processing.{cmd}"
            ssh_cmd         = f"ssh {self._user}@{self._host} '{self._command}'"

            # run command over ssh.
            try:
                out: Union[str, tuple[str, int]] = pexpect.run(ssh_cmd, encoding='utf-8',timeout=10)
                
                # Check for err msg
                if out[:4] in ['ireg', 'WARN', 'Erro'] and isinstance(out, str):
                    raise ExecError(f"Error from Libera BLM IOC:\n{out}")

            except pexpect.TIMEOUT:
                raise TimeoutError("Time out for restoring ADC window initial values. Initial values:\n"
                                   + f"adc_counter_offset_1 = {self.init_adc_offset_1},\n"
                                   + f"adc_counter_window_1 = {self.init_adc_window_1},\n"
                                   + f"adc_counter_offset_2 = {self.init_adc_offset_2},\n"
                                   + f"adc_counter_window_2 = {self.init_adc_window_2}."
                )

        # update values
        self.adc_offset_1 = self.init_adc_offset_1
        self.adc_window_1 = self.init_adc_window_1
        self.adc_offset_2 = self.init_adc_offset_2
        self.adc_window_2 = self.init_adc_window_2

        print("ADC window intial values restored!") 
    #
    # ----------------------------------------------------------------------------------------------------------
    def restore_default_adc_windows(self, ):
        """
        Restore default adc window values
        """

        # init commands
        commands = [
            f'adc_counter_mask1.offset={self._default_adc_offset_1}',
            f'adc_counter_mask1.window={self._default_adc_window_1}',
            f'adc_counter_mask2.offset={self._default_adc_offset_2}',
            f'adc_counter_mask2.window={self._default_adc_window_2}'
        ]

        # Can only assign one new value at a time so loop
        for cmd in commands:

            self._command   = f"libera-ireg access application.signal_processing.{cmd}"
            ssh_cmd         = f"ssh {self._user}@{self._host} '{self._command}'"

            try:
                # run command over ssh.
                out: Union[str, tuple[str, int]] = pexpect.run(ssh_cmd, encoding='utf-8',timeout=10)

                # Check for err msg
                if out[:4] in ['ireg', 'WARN', 'Erro'] and isinstance(out, str):
                    raise ExecError(f"Error from Libera BLM IOC:\n{out}")
                
            except pexpect.TIMEOUT:
                raise TimeoutError("Time out for restoring default adc window values. Default values:\n"
                                    + f"adc_counter_offset_1 = {self._default_adc_offset_1},\n"
                                    + f"adc_counter_window_1 = {self._default_adc_window_1},\n"
                                    + f"adc_counter_offset_2 = {self._default_adc_offset_2},\n"
                                    + f"adc_counter_window_2 = {self._default_adc_window_2}."
                )


        # update values
        self.adc_offset_1 = self._default_adc_offset_1
        self.adc_window_1 = self._default_adc_window_1
        self.adc_offset_2 = self._default_adc_offset_2
        self.adc_window_2 = self._default_adc_window_2

        print("ADC window default values restored!") 
    #
    # ----------------------------------------------------------------------------------------------------------
    def connect(self, ):
        """
        Connect to libera BLM for the first time.
        Assess whether the client's public ssh keys are on the server.
        If not, append users public keys to server's authorized_keys file in ~/.ssh/
        
        Possible future implementation:
        If authorized_keys does not exist (highly unlikely), gen the file from the client's public keys
        """

        
        # try to connect, see if you get an auth or password prompt
        auth, pwd = self._login()
        # if you do:
        if auth or pwd:
            # check if the concatenated public keys exist on the client
            public_key_exists: bool = True # default to True so don't accidentally regen public keys if check is somehow wrong


            try:
                check_cmd = "if test -f ~/.ssh/public_keys.$USER.$HOSTNAME; then echo '1'; else echo '0'; fi"

                # logs
                if self.__write_permissions:
                    self._logfile = open(os.path.join('libera_logs', 'connect.log'), 'w')
                    self._logfile.write(f'>> /bin/bash -c {check_cmd}\n')

                public_key_check = pexpect.spawn("/bin/bash", ['-c', check_cmd], encoding='utf-8', timeout=10, logfile=self._logfile)
                # convert output to str '0'/'1' to bool True/False
                if isinstance(public_key_check, str):
                    public_key_exists = bool(int(public_key_check))
                
                # if the public keys dont exist, generate them
                if not public_key_exists:
                    # logs
                    if self.__write_permissions:
                        self._logfile.write(">> massh keys\n")

                    pexpect.run("massh keys", encoding='utf-8', timeout=10, logfile=self._logfile)
                
                # add the client's public keys to the server's authorized_keys file
                copy_cmd = f"cat ~/.ssh/public_keys.$USER.$HOSTNAME | ssh {self._user}@{self._host} 'cat >> ~/.ssh/authorized_keys'"

                if self.__write_permissions:
                    self._logfile.write(f">> {copy_cmd}\n")

                # needs to open separate bash prompt ('-c') for usage of pipe ('|') character
                copy_keys = pexpect.spawn('/bin/bash', ['-c' ,copy_cmd], encoding='utf-8', timeout=10, logfile=self._logfile)

                # Wait for the password prompt and send the password
                password_prompt: int = copy_keys.expect("password:", timeout=1, )
                if password_prompt == 0:
                    copy_keys.sendline(self.__password)
            
                # Wait for the copy command to complete
                copy_keys.expect(pexpect.EOF)
                print('SSH keys copied!')

            finally:
                if self.__write_permissions:
                    self._logfile.close()

        print("Connected to Libera BLM")

        # # check if authorized_keys exists on server
        # try:
        #     authorized_keys_exists = True
        #     ssh_check_cmd = f"ssh {self._user}@{self._host} 'if test -f ~/.ssh/authorized_keys; then echo '1'; else echo '0'; fi'"
        #     authorized_keys_check = pexpect.spawn(ssh_check_cmd, encoding='utf-8', timeout=10)
        #     # wait for command to exec
        #     authorized_keys_check.expect(pexpect.EOF)
        #     # convert output to 0/1 True/False
        #     if authorized_keys_check.before is not None:
        #         authorized_keys_exists = int(authorized_keys_check.before)
        # except pexpect.TIMEOUT:
        #     raise TimeoutError("Public key check on client timed out.")
        # 
        # Will then have to copy public keys to ./ssh and use massh to generate authorized_keys on the server... 

    #
    # ----------------------------------------------------------------------------------------------------------
    def _login(self, ) -> tuple[bool, ...]:
        """
        Connect first time to the libera BLM system and deal with ssh authentication / password prompt

        returns booleans for auth check and password prompt (if asked)
        """

        # init returns
        auth: bool = False
        pwd:  bool = False

        ssh_cmd = f"ssh {self._user}@{self._host} 'echo $HOSTNAME'"

        # logs
        if self.__write_permissions:
            self._logfile = open(os.path.join('libera_logs', '_login.log'), 'w')
            self._logfile.write(f">> {ssh_cmd}\n")

        try:
            child = pexpect.spawn(ssh_cmd, encoding='utf-8', timeout=10, logfile=self._logfile)

            # Wait for authentication prompt (on first time ssh connect)
            auth_check: int = child.expect(['(?i)yes/no', 'password:', 'SR11IOC91'], timeout=5,)
            # if either of the first two options, go through the usual process of loggin in
            if auth_check < 2:
                if auth_check == 0:
                    # First time connection needs to clear `trusted' authentication flag
                    child.sendline("yes")
                    auth = True
                    child.expect(pexpect.EOF)
                # Wait for the password prompt and send the password
                child.sendline(self.__password)
                pwd = True

                # Wait for the command to complete
                child.expect(pexpect.EOF)

            elif auth_check == 2:
                print("Libera ssh connection already authenticated.")

        finally:
            if self.__write_permissions:
                self._logfile.close()
        
        return auth, pwd