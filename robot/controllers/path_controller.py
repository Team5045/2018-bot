from os import path
import pickle

import hal
from magicbot import StateMachine, state
import pathfinder as pf
from pathfinder.followers import DistanceFollower

from components import drivetrain
from controllers import angle_controller

if hal.HALIsSimulation():
    import pyfrc

SIM_PRINT_PATHS = False

MAX_VELOCITY = 3.66

# Drawing
CONV_Y = 3.28084
CONV_X = 3.28084
OFFSET_X = 1.5
OFFSET_Y = 1.25


class PathController(StateMachine):

    drivetrain = drivetrain.Drivetrain
    angle_controller = angle_controller.AngleController

    def setup(self):
        self.finished = False
        self.renderer = None

        self.left = DistanceFollower([])
        self.right = DistanceFollower([])

        # Argument format:
        # - P gain
        # - Integral gain (0)
        # - Derivative gain (tracking)
        # - Velocity ratio (1/max velo in trajectory config)
        # - Accel gain
        self.left.configurePIDVA(1, 0.0, 0.2, 1 / MAX_VELOCITY, 0)
        self.right.configurePIDVA(1, 0.0, 0.2, 1 / MAX_VELOCITY, 0)

    def set(self, _path, reverse=False):
        self.path = _path
        self.reverse = reverse
        print('[path controller] path set: %s' % _path)
        self.finished = False

    def is_finished(self):
        return self.finished

    def run(self):
        self.engage()

    @state(first=True)
    def prepare(self):
        self.drivetrain.shift_low_gear()
        self.drivetrain.set_manual_mode(True)
        self.drivetrain.reset_position()
        self.angle_controller.reset_angle()

        basepath = path.dirname(__file__)
        traj_path = path.abspath(path.join(basepath, '../paths', self.path))
        left_traj = pickle.load(open(traj_path + '-l.pickle', 'rb'))
        right_traj = pickle.load(open(traj_path + '-r.pickle', 'rb'))

        self.left.reset()
        self.right.reset()
        self.left.setTrajectory(left_traj)
        self.right.setTrajectory(right_traj)

        if SIM_PRINT_PATHS and hal.HALIsSimulation():
            traj = pickle.load(open(traj_path + '.pickle', 'rb'))
            self.renderer = pyfrc.sim.get_user_renderer()
            if self.renderer:
                y_offset = OFFSET_Y
                if self.reverse:
                    y_offset *= -1
                self.renderer.draw_pathfinder_trajectory(
                    left_traj,
                    color='blue',
                    scale=(CONV_X, CONV_Y),
                    offset=(-OFFSET_X, y_offset))
                self.renderer.draw_pathfinder_trajectory(
                    right_traj,
                    color='blue',
                    offset=(OFFSET_X, y_offset),
                    scale=(CONV_X, CONV_Y))
                self.renderer.draw_pathfinder_trajectory(
                    traj,
                    color='red',
                    offset=(0, y_offset),
                    scale=(CONV_X, CONV_Y))

        self.next_state('exec_path')

    @state
    def exec_path(self):
        # print('[path controller] [current] L: %s; R: %s' %
        # (self.drivetrain.get_left_encoder_meters(),
        #  self.drivetrain.get_right_encoder_meters()))

        l_dist = self.drivetrain.get_left_encoder_meters()
        r_dist = self.drivetrain.get_right_encoder_meters()

        if self.reverse:
            l_dist *= -1
            r_dist *= -1

        try:
            l_o = self.left.calculate(l_dist)
            r_o = self.right.calculate(r_dist)
        except Exception:
            return

        # print('[path controller] [calculated] L: %s; R: %s' % (l_o, r_o))

        gyro_heading = self.angle_controller.get_angle()
        desired_heading = -pf.r2d(self.left.getHeading())

        if self.reverse:
            desired_heading += 180

        # print('[path controller] [heading] curr: %s, desired: %s' % \
        # (gyro_heading, desired_heading))

        angleDifference = pf.boundHalfDegrees(desired_heading - gyro_heading)
        turn = 0.025 * angleDifference

        if self.reverse:
            turn *= -1

        # print('[path controller] [angle diff] %s' % (angleDifference))

        # print('[path controller] [calculated w turn] L: %s; R: %s' % \
        # (l_o + turn, r_o - turn))

        l_speed = l_o + turn
        r_speed = r_o - turn

        if self.reverse:
            l_speed *= -1
            r_speed *= -1

        self.drivetrain.manual_drive(l_speed, r_speed)

        if self.left.isFinished() and self.right.isFinished():
            self.stop()
            self.finished = True

    def stop(self):
        self.drivetrain.set_manual_mode(False)
        self.drivetrain.differential_drive(0)
        if self.renderer:
            self.renderer.clear()
            self.renderer = None
