"""What happens during one HTTP request (third-party-style example, M4 gate).

A protocol ``SequenceDiagram`` beside the server code (``AnimatedCode``) it executes:
each message highlights the lines that send or handle it. Sections become chapters in
the web player; cues mark the moments a narrator would talk over.

    manim-stage studio request.py Request
    manim-stage web request.py Request -q medium_quality
"""

from manim import DOWN, LEFT, RIGHT, UP, FadeIn, Text, Write

from manim_stage import AnimatedCode, StageScene
from manim_stage.edu import SequenceDiagram

HANDLER = """\
def get_user(request, user_id):
    if not request.session.valid:
        return Response(401)
    row = db.query("SELECT * FROM users WHERE id = ?", user_id)
    html = render("user.html", user=row)
    return Response(200, html)
"""


class Request(StageScene):
    def construct(self):
        title = Text("GET /users/42", font_size=36).to_edge(UP)
        diagram = (
            SequenceDiagram(
                ["browser", "server", "database"], spacing=2.4, height=5.2, font_size=22
            )
            .scale(0.85)
            .to_edge(LEFT)
            .shift(DOWN * 0.3)
        )
        code = AnimatedCode(HANDLER, font_size=16).to_edge(RIGHT).shift(DOWN * 0.2)

        self.next_section("Setup")
        self.play(Write(title), FadeIn(diagram), FadeIn(code))

        self.next_section("Request")
        self.cue("request_sent")
        self.play(diagram.message("browser", "server", "GET /users/42"), code.highlight_lines(1))
        self.play(code.highlight_lines(2, 3))

        self.next_section("Database")
        self.cue("query")
        self.play(diagram.message("server", "database", "SELECT …"), code.highlight_lines(4))
        self.play(diagram.message("database", "server", "row", reply=True))

        self.next_section("Response")
        self.cue("render")
        self.play(diagram.message("server", "server", "render"), code.highlight_lines(5))
        self.play(
            diagram.message("server", "browser", "200 OK", reply=True), code.highlight_lines(6)
        )
        self.play(code.reset_highlight())
        self.wait(0.5)
