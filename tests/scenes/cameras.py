from manim import DEGREES, RIGHT, Cube, Dot, Scene, Square, ThreeDScene, ZoomedScene


class Pan(Scene):
    def construct(self):
        self.add(Square(), Dot(RIGHT * 2))
        self.play(self.camera.frame.animate.scale(0.5).move_to(RIGHT * 2), run_time=1)


class Orbit(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=60 * DEGREES, theta=-30 * DEGREES)
        self.add(Cube())
        self.move_camera(theta=30 * DEGREES, run_time=1)


class Zoom(ZoomedScene):
    def construct(self):
        self.add(Dot())
        self.activate_zooming()
        self.wait(0.5)
