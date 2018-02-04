from collections import namedtuple
from controllers import position_controller, angle_controller

TrajectoryAction = namedtuple('TrajectoryAction',
                              ['rotate', 'position'])


class TrajectoryController:

    position_controller = position_controller.PositionController
    angle_controller = angle_controller.AngleController

    def __init__(self):
        self.actions = []
        self.current_action = None
        self.has_reset = False

    def push(self, rotate=None, position=None):
        self.actions.append(TrajectoryAction(rotate=rotate, position=position))

    def reset(self):
        self.actions = []
        self.current_action = None
        self.has_reset = False

    def is_finished(self):
        return len(self.actions) == 0

    def execute(self):
        if not self.current_action:
            if self.actions:
                self.current_action = self.actions.pop(0)
                self.has_reset = False
            else:
                self.position_controller.stop()
                self.angle_controller.stop()

        if self.current_action:
            if self.current_action.rotate:
                if not self.has_reset:
                    self.angle_controller.reset_angle()
                    self.has_reset = True
                else:
                    self.angle_controller.align_to(self.current_action.rotate)
                    if self.angle_controller.is_aligned():
                        self.current_action = None

            elif self.current_action.position:
                if not self.has_reset:
                    self.position_controller.reset_position_and_heading()
                    self.has_reset = True
                else:
                    self.position_controller.move_to(
                        self.current_action.position)
                    if self.position_controller.is_at_location():
                        self.current_action = None