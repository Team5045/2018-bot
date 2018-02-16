from robotpy_ext.autonomous import StatefulAutonomous, state, timed_state

from controllers.angle_controller import AngleController
from controllers.trajectory_controller import TrajectoryController
from components.drivetrain import Drivetrain
from components.elevator import Elevator, ElevatorPosition
from components.grabber import Grabber
from components.field import Field, SwitchState


class TwoCubeSide(StatefulAutonomous):

    DEFAULT = False
    ONE_CUBE_ONLY = False
    start_side = None

    angle_controller = AngleController
    trajectory_controller = TrajectoryController
    drivetrain = Drivetrain
    elevator = Elevator
    grabber = Grabber
    field = Field

    @state(first=True)
    def prepare_to_start(self):
        self.elevator.release_lock()
        self.elevator.raise_to_switch()
        self.trajectory_controller.reset()
        switch_side = self.field.get_switch_side()
        if switch_side is not None:
            self.sign = 1 if self.start_side == SwitchState.LEFT else -1
            if switch_side == self.start_side:
                self.trajectory_controller.push(position=228)
                self.trajectory_controller.push(rotate=90 * self.sign)
                self.trajectory_controller.push(position=60)
                self.trajectory_controller.push(rotate=90 * self.sign)
                self.trajectory_controller.push(position=10, timeout=3)
            else:
                self.trajectory_controller.push(position=228)
                self.trajectory_controller.push(rotate=90 * self.sign)
                self.trajectory_controller.push(position=175)
                self.trajectory_controller.push(rotate=90 * self.sign)
                self.trajectory_controller.push(position=10, timeout=3)
            self.next_state('execute_trajectory')

    @state
    def execute_trajectory(self):
        if self.trajectory_controller.is_finished():
            self.next_state('deposit')

    @timed_state(duration=3, next_state='back_up_to_hunt')
    def deposit(self):
        self.grabber.deposit()
        if self.ONE_CUBE_ONLY:
            self.done()

    @state
    def back_up_to_hunt(self):
        self.trajectory_controller.push(position=-20)
        self.trajectory_controller.push(position=45 * self.sign)
        self.trajectory_controller.push(position=10)
        self.next_state('execute_hunt_trajectory')

    @state
    def execute_hunt_trajectory(self):
        self.elevator.lower_to_ground()
        if self.trajectory_controller.is_finished() and \
                self.elevator.is_at_position(ElevatorPosition.GROUND):
            self.next_state('intake_second_cube')

    @timed_state(duration=1, next_state='rotate_back')
    def intake_second_cube(self):
        self.grabber.intake()

    def rotate_back(self):
        self.elevator.raise_to_switch()
        self.trajectory_controller.push(position=-10)
        self.trajectory_controller.push(position=-45 * self.sign)
        self.trajectory_controller.push(position=10, timeout=2)
        if self.trajectory_controller.is_finished() and \
                self.elevator.is_at_position(ElevatorPosition.SWITCH):
            self.next_state('execute_move_trajectory')

    @state
    def execute_move_trajectory(self):
        if self.trajectory_controller.is_finished():
            self.next_state('deposit_second_cube')

    @timed_state(duration=3)
    def deposit_second_cube(self):
        self.grabber.deposit()


class TwoCubeLeft(TwoCubeSide):

    MODE_NAME = 'Two Cube From Left'
    start_side = SwitchState.LEFT


class TwoCubeRight(TwoCubeSide):

    MODE_NAME = 'Two Cube From Right'
    start_side = SwitchState.RIGHT