"""How DNS spoofing (cache poisoning) works: an animated explainer.

A conceptual diagram, not a tool: boxes stand for the browser, the recursive resolver
(with its cache), the authoritative name server for example.com, the real web server
and an attacker. DNS messages are labelled cards that travel between them.

1. **Normal lookup:** the resolver asks, checks the reply's transaction ID, caches the
   answer for its TTL, and the browser reaches the real server.
2. **Cache poisoning:** once the record expires, an attacker makes the resolver look
   the name up again and races the real reply with forged ones, each guessing the
   16-bit transaction ID. A guess that matches first is cached.
3. **Victim redirected:** later users get the poisoned answer straight from the cache;
   the HTTPS certificate check is what still gives the fake site away.
4. **Defenses:** random IDs and ports, DNSSEC, encrypted DNS, HTTPS.

Addresses are documentation ranges (RFC 5737); example.com is reserved for examples.

manim-stage features used: ``self.cue`` at each narration moment, sections (chapters
in the web player), a ``Signal`` for the TTL countdown, ``sequence``/``chain`` for the
packet race, and colours from ``.manim-stage/project.json``.

    manim-stage studio dns_spoofing.py DnsSpoofing
    manim-stage web dns_spoofing.py DnsSpoofing -q medium_quality
"""

import numpy as np
from manim import (
    DOWN,
    LEFT,
    PI,
    RIGHT,
    UP,
    Arc,
    Arrow,
    Circumscribe,
    Create,
    FadeIn,
    FadeOut,
    Indicate,
    Line,
    ManimColor,
    RoundedRectangle,
    Text,
    Transform,
    VGroup,
    Write,
    always_redraw,
    interpolate_color,
)

from manim_stage import Signal, StageScene, chain, project, sequence

REAL_IP = "198.51.100.10"
EVIL_IP = "203.0.113.66"


def node(name: str, detail: str, color: str, *, width: float = 3.2) -> VGroup:
    """A labelled box standing for one machine."""
    box = RoundedRectangle(
        corner_radius=0.12, width=width, height=1.15, color=color, fill_opacity=0.12
    )
    title = Text(name, font_size=20, weight="BOLD")
    sub = Text(detail, font_size=16, color=color)
    labels = VGroup(title, sub).arrange(DOWN, buff=0.12).move_to(box)
    return VGroup(box, labels)


def packet(label: str, color: str) -> VGroup:
    """A DNS message drawn as a small opaque card (``label`` may have two lines)."""
    text = Text(label, font_size=15, line_spacing=0.8)
    card = RoundedRectangle(
        corner_radius=0.06,
        width=text.width + 0.24,
        height=text.height + 0.2,
        color=color,
        fill_color=interpolate_color(
            ManimColor(project.theme().background), ManimColor(color), 0.3
        ),
        fill_opacity=1,
        stroke_width=2,
    )
    return VGroup(card, text.move_to(card))


def route(points, color: str) -> VGroup:
    """An arrow that follows a path of corner points."""
    segs = [
        Line(a, b, color=color, stroke_width=3)
        for a, b in zip(points[:-2], points[1:-1], strict=True)
    ]
    tip = Arrow(points[-2], points[-1], buff=0, color=color, stroke_width=3)
    tip.tip.scale(0.7)
    return VGroup(*segs, tip)


def padlock(color: str, *, broken: bool = False) -> VGroup:
    body = RoundedRectangle(
        corner_radius=0.04, width=0.34, height=0.26, color=color, fill_opacity=0.9
    )
    shackle = Arc(radius=0.11, start_angle=0, angle=PI, color=color, stroke_width=5)
    shackle.next_to(body, UP, buff=0)
    if broken:
        shackle.rotate(0.6, about_point=shackle.get_start()).shift(UP * 0.06)
    return VGroup(body, shackle)


def ends(pkt: VGroup, frm, to, gap: float = 0.08):
    """Start and end centres for ``pkt`` travelling from point ``frm`` to point ``to``,
    so that it never covers the boxes those points sit on."""
    frm, to = np.array(frm, dtype=float), np.array(to, dtype=float)
    d = (to - frm) / np.linalg.norm(to - frm)
    reach = abs(d[0]) * pkt.width / 2 + abs(d[1]) * pkt.height / 2 + gap
    return frm + d * reach, to - d * reach


class DnsSpoofing(StageScene):
    def construct(self):
        theme = project.theme()
        ok, bad, info, muted = theme.success, theme.error, theme.accent, theme.muted

        title = Text("DNS spoofing: how cache poisoning works", font_size=30)
        title.to_edge(UP, buff=0.3)

        browser = node("Browser", "user's laptop", theme.primary, width=2.3)
        browser.move_to([-5.6, 1.5, 0])
        resolver = node("Recursive resolver", "ISP / office DNS", theme.primary)
        resolver.move_to([-1.0, 1.5, 0])
        auth = node("Authoritative DNS", "name server for example.com", theme.primary)
        auth.move_to([5.0, 2.2, 0])
        web = node("example.com", f"web server {REAL_IP}", ok).move_to([5.0, 0.3, 0])
        attacker = node("Attacker", EVIL_IP, bad).move_to([5.0, -1.6, 0])

        cache_box = RoundedRectangle(
            corner_radius=0.1, width=5.9, height=0.8, color=muted, stroke_width=2
        ).move_to([-1.0, -0.2, 0])
        cache_head = Text("resolver cache", font_size=16, color=muted)
        cache_head.next_to(cache_box, UP, buff=0.06).align_to(cache_box, LEFT).shift(RIGHT * 0.1)

        def cache_row(ip: str, color: str, ttl: str = "TTL 300") -> VGroup:
            row = VGroup(
                Text("example.com", font_size=18),
                Text("A", font_size=18, color=muted),
                Text(ip, font_size=18, color=color),
                Text(ttl, font_size=18, color=muted),
            ).arrange(RIGHT, buff=0.35)
            return row.move_to(cache_box).align_to(cache_box, LEFT).shift(RIGHT * 0.25)

        caption = [Text(" ", font_size=22).to_edge(DOWN, buff=0.35)]

        def say(text: str):
            """Swap the caption at the bottom of the frame."""
            old, new = caption[0], Text(text, font_size=22).to_edge(DOWN, buff=0.35)
            caption[0] = new
            return chain(FadeOut(old, run_time=0.25), FadeIn(new, run_time=0.35))

        def send(label: str, color: str, frm, to, run_time: float = 0.9):
            """Play a packet travelling between two points; return it."""
            pkt = packet(label, color)
            start, end = ends(pkt, frm, to)
            pkt.move_to(start)
            self.play(FadeIn(pkt, scale=0.6), run_time=0.25)
            self.play(pkt.animate.move_to(end), run_time=run_time)
            return pkt

        # Points on the boxes where messages leave and arrive.
        b_out, r_in = browser.get_right(), resolver.get_left()
        r_up, r_down = resolver.get_right() + UP * 0.3, resolver.get_right() + DOWN * 0.25
        a_in = auth.get_left()
        x_out = attacker.get_left()

        # ------------------------------------------------------------ 1: normal lookup
        self.next_section("Normal lookup")
        self.play(Write(title), run_time=1)
        self.play(
            sequence(0.15, *(FadeIn(m, shift=UP * 0.2) for m in (browser, resolver, auth, web))),
            FadeIn(cache_box),
            FadeIn(cache_head),
        )
        self.play(say("Your browser needs the IP address of example.com"))

        self.cue("lookup_starts")
        self.play(say("It asks the recursive resolver for the A record"))
        q = send("A? example.com", info, b_out, r_in)
        self.play(FadeOut(q), Indicate(cache_box, color=muted, scale_factor=1.05), run_time=0.6)

        self.play(say("Not cached, so the resolver asks example.com's name server"))
        q = send("A? example.com\nid 0x3a7f", info, r_up, a_in)
        self.play(FadeOut(q), run_time=0.3)

        reply = send(f"A {REAL_IP}\nid 0x3a7f", ok, a_in, r_up)
        self.play(say("The reply's transaction ID matches the question, so it is accepted"))
        self.play(Circumscribe(reply, color=ok), run_time=0.8)

        self.cue("answer_cached")
        ttl = Signal(300)
        good_row = cache_row(REAL_IP, ok)
        ttl_slot = good_row[3]
        ttl_text = always_redraw(
            lambda: Text(f"TTL {int(ttl())}", font_size=18, color=muted).move_to(
                ttl_slot, aligned_edge=LEFT
            )
        )
        self.play(
            say("…and cached for its time to live (TTL): 300 seconds"),
            Transform(reply, good_row[:3]),
            FadeIn(ttl_text),
        )
        self.remove(reply)
        self.add(good_row[:3])

        ans = send(REAL_IP, ok, r_in, b_out)
        to_web = route(
            [
                browser.get_bottom(),
                [-5.6, -1.9, 0],
                [2.8, -1.9, 0],
                [2.8, 0.3, 0],
                web.get_left(),
            ],
            ok,
        )
        lock = padlock(ok).next_to(browser, UP, buff=0.1).align_to(browser, RIGHT)
        self.play(FadeOut(ans), Create(to_web), say("The browser connects to the real server"))
        self.play(FadeIn(lock, scale=0.5), Indicate(web, color=ok, scale_factor=1.05))
        self.wait(0.6)
        self.play(FadeOut(to_web), FadeOut(lock))

        # ------------------------------------------------------------ 2: cache poisoning
        self.next_section("Cache poisoning")
        self.cue("ttl_expired")
        self.play(say("Later, the cached record expires"))
        self.play(ttl.animate.set_value(0), run_time=1.5)
        self.play(FadeOut(good_row[:3]), FadeOut(ttl_text))

        self.play(
            FadeIn(attacker, shift=LEFT * 0.3),
            say("An attacker asks the resolver for example.com, forcing a new lookup…"),
        )
        att_q = send("A? example.com", bad, x_out, r_down)
        self.play(FadeOut(att_q), run_time=0.3)
        q = send("A? example.com\nid 0x9c21", info, r_up, a_in)
        waiting = Text("waiting for id 0x9c21", font_size=17, color=info)
        waiting.next_to(resolver, UP, buff=0.15)
        self.play(FadeOut(q), FadeIn(waiting), run_time=0.5)

        self.cue("flood")
        self.play(say("…then races the real reply with forged ones, guessing the 16-bit ID"))
        guesses = ["0x0001", "0x51f0", "0x7a2c", "0xe013", "0x9c21"]
        forged = [packet(f"A {EVIL_IP}\nid {g}", bad) for g in guesses]
        start = ends(forged[0], x_out, r_down)[0]
        land = np.array([1.5, 0.95, 0])
        real = packet(f"A {REAL_IP}\nid 0x9c21", ok)
        real_start, real_end = ends(real, a_in, r_up)
        real.move_to(real_start)

        # Forged replies land in a pile next to the resolver, one every 0.45 s
        # (FadeIn with a shift travels from ``start`` to the pile while fading in).
        spots = [land + np.array([0.18 * k, -0.05 * k, 0]) for k in range(len(forged))]
        for p, spot in zip(forged, spots, strict=True):
            p.move_to(spot)
        self.play(
            sequence(
                0.45,
                *(
                    FadeIn(p, shift=s - start, run_time=0.7)
                    for p, s in zip(forged, spots, strict=True)
                ),
            ),
            chain(
                FadeIn(real, run_time=0.3),
                real.animate(run_time=2.4).move_to(real_start + (real_end - real_start) * 0.45),
            ),
        )
        wrong, winner = VGroup(*forged[:-1]), forged[-1]
        match = Text("id matches", font_size=16, color=info).next_to(winner, UP, buff=0.08)
        self.play(
            wrong.animate.set_color(muted).set_opacity(0.35),
            winner[0].animate.set_stroke(info, width=4),
            FadeIn(match),
            say("Wrong guesses are dropped, but one matches before the real reply arrives"),
        )
        self.play(FadeOut(wrong, shift=DOWN * 0.2), run_time=0.4)

        self.cue("poisoned")
        bad_row = cache_row(EVIL_IP, bad, "TTL 86400")
        self.play(
            FadeOut(waiting),
            FadeOut(match),
            Transform(winner, bad_row),
            say("The resolver caches the attacker's address, with a long TTL"),
        )
        self.remove(winner)
        self.add(bad_row)
        late = Text("too late: already answered", font_size=16, color=muted)
        self.play(real.animate.move_to(real_end), run_time=0.6)
        late.next_to(real, DOWN, buff=0.1)
        self.play(FadeIn(late), real.animate.set_opacity(0.3))
        self.play(FadeOut(real), FadeOut(late))

        # ------------------------------------------------------------ 3: victim redirected
        self.next_section("Victim redirected")
        self.cue("victim_asks")
        self.play(say("Now every user of this resolver gets the poisoned answer from its cache"))
        q = send("A? example.com", info, b_out, r_in)
        self.play(FadeOut(q), Indicate(bad_row, color=bad), run_time=0.6)
        ans = send(EVIL_IP, bad, r_in, b_out)

        fake = node("example.com ?", f"look-alike site {EVIL_IP}", bad).move_to(attacker)
        to_fake = route([browser.get_bottom(), [-5.6, -1.6, 0], attacker.get_left()], bad)
        self.play(
            FadeOut(ans),
            Create(to_fake),
            Transform(attacker, fake),
            say("The browser connects to the attacker's look-alike site instead"),
        )

        self.cue("cert_warning")
        broken = padlock(bad, broken=True).next_to(browser, UP, buff=0.1)
        broken.align_to(browser, RIGHT)
        warn = Text("certificate is not\nfor example.com", font_size=16, color=bad)
        warn.next_to(broken, LEFT, buff=0.15)
        self.play(
            FadeIn(broken, scale=0.5),
            FadeIn(warn),
            say("Over HTTPS the fake site can't prove it is example.com, so the browser warns"),
        )
        self.wait(0.8)
        self.play(say("Over plain HTTP nothing warns: the user just sees a convincing copy"))
        self.wait(1)

        # ------------------------------------------------------------ 4: defenses
        self.next_section("Defenses")
        self.cue("defenses")
        diagram = VGroup(
            browser, resolver, auth, web, attacker, cache_box, cache_head, bad_row, to_fake
        )
        self.play(FadeOut(diagram), FadeOut(broken), FadeOut(warn), say("Defenses work in layers"))

        cards = [
            ("Random ID and source port", "about 4 billion combinations\nto guess, not 65,536"),
            ("DNSSEC", "the zone signs its records;\na validating resolver drops forgeries"),
            ("DNS over TLS / HTTPS", "encrypts and authenticates\nbrowser ↔ resolver traffic"),
            ("HTTPS certificates", "a wrong address still can't\nprove it is example.com"),
        ]
        tiles = VGroup()
        for head, body in cards:
            box = RoundedRectangle(
                corner_radius=0.12, width=5.6, height=1.9, color=ok, fill_opacity=0.08
            )
            text = VGroup(
                Text(head, font_size=24, weight="BOLD", color=ok),
                Text(body, font_size=19, line_spacing=0.9),
            ).arrange(DOWN, buff=0.18)
            tiles.add(VGroup(box, text.move_to(box)))
        tiles.arrange_in_grid(rows=2, cols=2, buff=(0.4, 0.35)).shift(DOWN * 0.15)
        self.play(sequence(0.3, *(FadeIn(t, shift=UP * 0.2) for t in tiles)))
        self.wait(0.5)
        for tile in tiles:
            self.play(Indicate(tile[0], color=info, scale_factor=1.03), run_time=0.6)
        self.play(say("Make guessing impractical, verify answers, protect the last hop"))
        self.wait(1.5)
