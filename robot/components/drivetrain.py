import math
from collections import namedtuple
from ctre import WPI_TalonSRX
from wpilib import Solenoid
from wpilib.drive import DifferentialDrive
from magicbot import tunable
from robotpy_ext.common_drivers import navx

from constants import TALON_TIMEOUT
from common import util

DifferentialDriveConfig = namedtuple('DifferentialDriveConfig',
                                     ['y', 'rotation', 'squared',
                                      'quick_turn'])

HIGH_GEAR = False
LOW_GEAR = True

UNITS_PER_REV = 4096
DISTANCE_PER_REV = (2 * math.pi * 3) / (3 / 1) / (54 / 30)
DISTANCE_PER_REV_METERS = (2 * math.pi * 0.0762) / (3 / 1) / (54 / 30)

DEADBAND = 0.05


class Drivetrain:

    navx = navx.AHRS

    left_motor_master = WPI_TalonSRX
    left_motor_slave = WPI_TalonSRX
    right_motor_master = WPI_TalonSRX
    right_motor_slave = WPI_TalonSRX

    shifter_solenoid = Solenoid

    arcade_cutoff = tunable(0.1)
    angle_correction_cutoff = tunable(0.05)
    angle_correction_factor_low_gear = tunable(0.1)
    angle_correction_factor_high_gear = tunable(0.1)
    angle_correction_max = tunable(0.2)

    little_rotation_cutoff = tunable(0.1)

    def setup(self):
        self.pending_differential_drive = None
        self.force_differential_drive = False
        self.pending_gear = LOW_GEAR
        self.pending_position = None
        self.pending_reset = False
        self.og_yaw = None
        self.pending_manual_drive = None
        self.is_manual_mode = False

        # Set encoders
        self.left_motor_master.configSelectedFeedbackSensor(
            WPI_TalonSRX.FeedbackDevice.CTRE_MagEncoder_Relative, 0, 0)
        self.right_motor_master.configSelectedFeedbackSensor(
            WPI_TalonSRX.FeedbackDevice.CTRE_MagEncoder_Relative, 0, 0)
        self.left_motor_master.setSensorPhase(True)

        # Set slave motors
        self.left_motor_slave.set(WPI_TalonSRX.ControlMode.Follower,
                                  self.left_motor_master.getDeviceID())
        self.right_motor_slave.set(WPI_TalonSRX.ControlMode.Follower,
                                   self.right_motor_master.getDeviceID())

        # Set up drive control
        self.robot_drive = DifferentialDrive(self.left_motor_master,
                                             self.right_motor_master)
        self.robot_drive.setDeadband(0)
        self.robot_drive.setSafetyEnabled(False)

    def reset_position(self):
        self.left_motor_master.setQuadraturePosition(0, TALON_TIMEOUT)
        self.right_motor_master.setQuadraturePosition(0, TALON_TIMEOUT)

    def get_position(self):
        '''
        Returns averaged quadrature position in inches.
        '''
        left_position = -self.left_motor_master.getQuadraturePosition()
        right_position = self.right_motor_master.getQuadraturePosition()
        return (((left_position + right_position) / 2) *
                (1 / UNITS_PER_REV) * DISTANCE_PER_REV)

    def drive(self, *args):
        self.differential_drive(*args)

    def differential_drive(self, y, rotation=0, squared=True, force=False,
                           quick_turn=False):
        if not self.force_differential_drive:
            self.pending_differential_drive = DifferentialDriveConfig(
                y=y, rotation=rotation, squared=squared, quick_turn=quick_turn)
            self.force_differential_drive = force

    def turn(self, rotation=0, force=False):
        self.differential_drive(0, rotation, squared=False, force=force)

    def reset_angle_correction(self):
        self.navx.reset()

    def angle_corrected_differential_drive(self, y, rotation=0):
        '''
        Heading must be reset first. (drivetrain.reset_angle_correction())
        '''

        # Angle correction
        if abs(rotation) <= self.angle_correction_cutoff:
            heading = self.navx.getYaw()
            if not self.og_yaw:
                self.og_yaw = heading
            factor = self.angle_correction_factor_high_gear if \
                self.pending_gear == HIGH_GEAR else \
                self.angle_correction_factor_low_gear
            rotation = util.abs_clamp(-factor *
                                      (heading - self.og_yaw),
                                      0, self.angle_correction_max)
        else:
            self.og_yaw = None

        # Small rotation at lower speeds
        if abs(y) <= self.little_rotation_cutoff:
            rotation = util.abs_clamp(rotation, 0, 0.75)

        self.differential_drive(y, rotation)

    def shift_low_gear(self):
        self.pending_gear = LOW_GEAR

    def shift_high_gear(self):
        self.pending_gear = HIGH_GEAR

    def shift_toggle(self):
        if self.pending_gear == HIGH_GEAR:
            self.pending_gear = LOW_GEAR
        else:
            self.pending_gear = HIGH_GEAR

    def manual_drive(self, left, right):
        self.pending_manual_drive = [left, right]

    def get_left_encoder(self):
        return -self.left_motor_master.getQuadraturePosition()

    def get_right_encoder(self):
        return self.right_motor_master.getQuadraturePosition()

    def get_left_encoder_meters(self):
        return self.get_left_encoder() * \
            (1 / UNITS_PER_REV) * DISTANCE_PER_REV_METERS

    def get_right_encoder_meters(self):
        return self.get_right_encoder() * \
            (1 / UNITS_PER_REV) * DISTANCE_PER_REV_METERS

    def set_manual_mode(self, is_manual):
        self.is_manual_mode = is_manual

    def execute(self):
        # print('dist_traveled_meters', self.get_left_encoder_meters(),
        #       self.get_right_encoder_meters())

        # Shifter
        self.shifter_solenoid.set(self.pending_gear)

        # Manual
        if self.is_manual_mode:
            if self.pending_manual_drive:
                left, right = self.pending_manual_drive
                left = self.robot_drive.applyDeadband(left, DEADBAND)
                right = self.robot_drive.applyDeadband(right, DEADBAND)
                self.left_motor_master.set(-left)
                self.right_motor_master.set(right)
                self.pending_manual_drive = None
            return

        # Drive
        if self.pending_differential_drive:
            if self.pending_gear == LOW_GEAR or \
                    abs(self.pending_differential_drive.y) <= \
                    self.arcade_cutoff:
                self.robot_drive.arcadeDrive(
                    self.pending_differential_drive.y,
                    -self.pending_differential_drive.rotation,
                    squaredInputs=self.pending_differential_drive.squared)
            elif self.pending_gear == HIGH_GEAR:
                self.robot_drive.curvatureDrive(
                    self.pending_differential_drive.y,
                    -self.pending_differential_drive.rotation,
                    isQuickTurn=self.pending_differential_drive.quick_turn)

            self.pending_differential_drive = None
            self.force_differential_drive = False

    def on_disable(self):
        self.robot_drive.arcadeDrive(0, 0)

    def get_state(self):
        return {
            'pending_gear': self.pending_gear,
            'pending_differential_drive': self.pending_differential_drive
        }

    def put_state(self, state):
        self.pending_gear = state['pending_gear']
        self.pending_differential_drive = DifferentialDriveConfig._make(
            state['pending_differential_drive'])
