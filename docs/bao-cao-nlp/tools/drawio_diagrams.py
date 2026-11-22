"""Sinh các sơ đồ draw.io (mxGraph XML) của báo cáo vào figures/drawio/*.drawio.

Mỗi tệp mở và chỉnh sửa được bằng draw.io / app.diagrams.net. Xuất PNG bằng draw.io desktop:
    draw.io.exe -x -f png -s 2 -b 10 -o figures/<tên>.png figures/drawio/<tên>.drawio
(script export_drawio.ps1 cùng thư mục làm việc này cho mọi tệp).
"""

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "figures" / "drawio"
FONT = "fontFamily=Times New Roman;fontSize=14;"
S = {
    "box": "rounded=1;whiteSpace=wrap;html=1;fillColor=#DEEAF6;strokeColor=#1F4E79;" + FONT,
    "key": "rounded=1;whiteSpace=wrap;html=1;fillColor=#9DC3E6;strokeColor=#1F4E79;fontStyle=1;" + FONT,
    "ext": "rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF2CC;strokeColor=#BF9000;" + FONT,
    "ok": "rounded=1;whiteSpace=wrap;html=1;fillColor=#E2F0D9;strokeColor=#548235;" + FONT,
    "warn": "rounded=1;whiteSpace=wrap;html=1;fillColor=#FBE5D6;strokeColor=#C55A11;" + FONT,
    "db": "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=12;fillColor=#EDEDED;strokeColor=#595959;" + FONT,
    "dec": "rhombus;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#1F4E79;" + FONT,
    "term": "ellipse;whiteSpace=wrap;html=1;fillColor=#1F4E79;fontColor=#FFFFFF;strokeColor=#1F4E79;" + FONT,
    "actor": "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;" + FONT,
    "uc": "ellipse;whiteSpace=wrap;html=1;fillColor=#DEEAF6;strokeColor=#1F4E79;" + FONT,
    "group": "rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor=none;strokeColor=#7F7F7F;verticalAlign=top;align=left;spacingLeft=8;fontStyle=2;" + FONT,
    "lane": "swimlane;horizontal=0;whiteSpace=wrap;html=1;startSize=34;fillColor=#F2F2F2;strokeColor=#7F7F7F;fontStyle=1;" + FONT,
    "table": "rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;spacingLeft=6;fillColor=#FFFFFF;strokeColor=#1F4E79;" + FONT.replace("14", "13"),
    "note": "shape=note;whiteSpace=wrap;html=1;size=12;fillColor=#FFFFFF;strokeColor=#7F7F7F;" + FONT.replace("14", "13"),
    "life": "shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=0;collapsible=0;size=40;fillColor=#DEEAF6;strokeColor=#1F4E79;fontStyle=1;" + FONT,
    "text": "text;html=1;align=center;verticalAlign=middle;" + FONT,
}
E = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeColor=#262626;" + FONT.replace("14", "12") + "labelBackgroundColor=#FFFFFF;"
ES = "html=1;endArrow=block;endFill=1;strokeColor=#262626;" + FONT.replace("14", "12") + "labelBackgroundColor=#FFFFFF;"


class D:
    def __init__(self, name):
        self.name, self.cells, self.n = name, [], 0

    def v(self, key, label, x, y, w=160, h=56, style="box", extra=""):
        self.cells.append(
            f'<mxCell id="{key}" value="{escape(label, {chr(34): "&quot;"})}" style="{S.get(style, style)}{extra}" '
            f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return key

    def e(self, a, b, label="", style=None, extra="", pts=()):
        self.n += 1
        geo = '<mxGeometry relative="1" as="geometry">'
        if pts:
            geo += "<Array as=\"points\">" + "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts) + "</Array>"
        geo += "</mxGeometry>"
        self.cells.append(
            f'<mxCell id="e{self.n}" value="{escape(label)}" style="{style or E}{extra}" edge="1" parent="1" '
            f'source="{a}" target="{b}">{geo}</mxCell>')

    def line(self, x1, y1, x2, y2, label="", extra=""):
        """Mũi tên tự do (cho sơ đồ tuần tự)."""
        self.n += 1
        self.cells.append(
            f'<mxCell id="l{self.n}" value="{escape(label)}" style="{ES}{extra}" edge="1" parent="1">'
            f'<mxGeometry relative="1" as="geometry"><mxPoint x="{x1}" y="{y1}" as="sourcePoint"/>'
            f'<mxPoint x="{x2}" y="{y2}" as="targetPoint"/></mxGeometry></mxCell>')

    def save(self):
        OUT.mkdir(parents=True, exist_ok=True)
        xml = ('<mxfile host="drawio"><diagram name="' + self.name + '"><mxGraphModel grid="1" gridSize="10" '
               'page="0" background="#FFFFFF"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
               + "".join(self.cells) + "</root></mxGraphModel></diagram></mxfile>")
        (OUT / f"{self.name}.drawio").write_text(xml, encoding="utf-8")


def rag_pipeline():
    d = D("rag_pipeline")
    d.v("g1", "Giai đoạn ngoại tuyến (lập chỉ mục)", 0, 0, 900, 120, "group")
    d.v("g2", "Giai đoạn trực tuyến (hỏi đáp)", 0, 160, 900, 120, "group")
    xs = [20, 240, 460, 680]
    for i, (k, t, st) in enumerate([("a", "Tài liệu nguồn", "box"), ("b", "Làm sạch và chia đoạn", "box"),
                                    ("c", "Mã hóa (embedding)", "box"), ("idx", "Chỉ mục vector", "db")]):
        d.v(k, t, xs[i], 40, 190, 64, st)
    for i, (k, t) in enumerate([("q", "Câu hỏi"), ("r", "Truy xuất top-k"), ("p", "Ghép đoạn vào prompt"), ("l", "LLM sinh câu trả lời")]):
        d.v(k, t, xs[i], 200, 190, 64, "key" if k == "l" else "box")
    for a, b in [("a", "b"), ("b", "c"), ("c", "idx"), ("q", "r"), ("r", "p"), ("p", "l")]:
        d.e(a, b)
    d.e("idx", "r", "tìm đoạn gần nhất", pts=[(775, 140), (335, 140)])
    d.save()


def react_loop():
    d = D("react_loop")
    d.v("q", "Câu hỏi", 0, 60, 130, 56, "term")
    d.v("t", "Suy nghĩ (Thought)", 200, 60, 180, 56, "key")
    d.v("a", "Hành động (Action):<br>gọi công cụ", 460, 60, 190, 56)
    d.v("o", "Quan sát (Observation):<br>kết quả công cụ", 460, 200, 190, 56, "ext")
    d.v("f", "Câu trả lời cuối", 200, 200, 180, 56, "ok")
    d.e("q", "t"); d.e("t", "a")
    d.e("a", "o", "công cụ chạy")
    d.e("o", "t", "chưa đủ: lặp lại", pts=[(420, 228), (420, 150), (330, 150)])
    d.e("t", "f", "đủ thông tin", extra="exitX=0.25;exitY=1;entryX=0.25;entryY=0;")
    d.save()


def workflow_online():
    """Quy trình nghiệp vụ dạng làn bơi: Người chơi / Giao diện + API / Agent / Bộ sinh và kiểm tra."""
    d = D("workflow_online")
    W = 1180
    lanes = [("Người chơi", 110), ("Web / Discord + API", 120), ("Agent (LangGraph)", 230), ("Bộ sinh và kiểm tra", 120)]
    y = 0
    ly = {}
    for name, h in lanes:
        d.v("L" + str(len(ly)), name, 0, y, W, h, "lane")
        ly[name] = y
        y += h
    yp, ya, yg, yc = ly["Người chơi"], ly["Web / Discord + API"], ly["Agent (LangGraph)"], ly["Bộ sinh và kiểm tra"]
    d.v("start", "Đặt câu hỏi", 40, yp + 30, 140, 50, "term")
    d.v("api", "Xác thực, giới hạn tần suất,<br>hạn mức ngày", 50, ya + 32, 190, 58)
    d.v("mem", "Nạp ký ức và<br>các lượt gần đây", 280, ya + 32, 170, 58)
    d.v("ag", "Agent phân tích ý định,<br>chọn công cụ", 280, yg + 30, 190, 62, "key")
    d.v("tools", "Thực thi công cụ: tìm kho, kiểm tên,<br>mở bằng chứng, tìm web,<br>ghi điều kiện, run_python", 520, yg + 20, 250, 82, "ext")
    d.v("dec", "Kết thúc<br>bằng?", 300, yg + 130, 150, 84, "dec")
    d.v("ask", "Câu hỏi lại<br>(ask_user)", 50, yg + 146, 160, 52, "warn")
    d.v("rep", "Trả lời ngắn<br>(reply)", 520, yg + 146, 160, 52)
    d.v("ctx", "Dựng ngữ cảnh:<br>≤ 5 bằng chứng Agent chọn", 820, yg + 140, 220, 62)
    d.v("gen", "Sinh JSON có trích dẫn", 820, yc + 10, 220, 46)
    d.v("chk", "Kiểm trích dẫn nguyên văn,<br>sinh lại ≤ 1, Answer Guard", 520, yc + 10, 250, 56)
    d.v("img", "Chọn ảnh<br>(song song)", 1060, yc + 10, 110, 56, "note")
    d.v("out", "Nhận câu trả lời<br>kèm nguồn, ảnh", 830, yp + 26, 190, 58, "ok")
    d.v("reply2", "Trả lời câu hỏi lại<br>(lượt mới)", 230, yp + 28, 170, 54, "warn")
    d.e("start", "api"); d.e("api", "mem"); d.e("mem", "ag")
    d.e("ag", "tools", "gọi", extra="exitY=0.35;entryY=0.35;")
    d.e("tools", "ag", "kết quả", extra="exitY=0.75;entryY=0.75;")
    d.e("ag", "dec")
    d.e("dec", "ask", "ask_user"); d.e("dec", "rep", "reply")
    d.e("dec", "ctx", "finish", pts=[(375, yg + 225), (930, yg + 225)])
    d.e("ctx", "gen"); d.e("gen", "chk")
    d.e("gen", "img", extra="dashed=1;")
    d.e("chk", "out", "hợp lệ", pts=[(795, yc + 38), (795, yp + 55)], extra="exitX=1;exitY=0.5;entryX=0;entryY=0.5;")
    d.e("rep", "out", pts=[(795, yg + 172), (795, yp + 55)], extra="exitX=1;exitY=0.5;entryX=0;entryY=0.5;")
    d.e("ask", "reply2", "gửi thẳng cho người chơi", pts=[(130, ya + 112), (255, ya + 112)], extra="exitX=0.5;exitY=0;entryX=0.147;entryY=1;")
    d.e("reply2", "api", "", extra="dashed=1;exitX=0;exitY=0.5;entryX=0.84;entryY=0;", pts=[(210, yp + 55)])
    d.save()


def clarify_sequence():
    d = D("clarify_sequence")
    cols = {"p": ("Người chơi", 60), "s": ("Máy chủ", 400), "a": ("Agent", 740)}
    for k, (t, x) in cols.items():
        d.v(k, t, x - 70, 0, 140, 600, "life")
    msgs = [
        ("p", "s", "“Build cho nhân vật của tôi”"),
        ("s", "a", "câu hỏi + ký ức + lượt gần đây"),
        ("a", "s", "ask_user(level, lớp nhân vật)"),
        (None, "s", "Lưu yêu cầu chờ, hạn 30 phút"),
        ("s", "p", "câu hỏi lại"),
        ("p", "s", "“level 80, Samurai” + mã yêu cầu"),
        ("s", "a", "câu gốc + câu hỏi lại + câu trả lời"),
        (None, "a", "set_conditions → tìm kiếm → run_python → finish"),
        ("a", "s", "bằng chứng + kết quả tính"),
        ("s", "p", "câu trả lời có trích dẫn"),
    ]
    y = 80
    for a, b, t in msgs:
        if a is None:
            x = cols[b][1]
            d.v(f"n{y}", t, x - (180 if b == "a" else 20), y - 18, 230 if b == "a" else 220, 36, "note")
        else:
            d.line(cols[a][1], y, cols[b][1], y, t, extra="verticalAlign=bottom;" + ("dashed=1;" if a != "p" and b == "p" else ""))
        y += 52
    d.save()


def offline_pipeline():
    d = D("offline_pipeline")
    steps = [("c", "1. Thu thập<br>(crawl)"), ("f", "2. Lọc<br>(filter)"), ("t", "3. Biến đổi<br>(transform)"),
             ("k", "4. Chia đoạn<br>(chunk, 450 token)"), ("i", "5. Lập chỉ mục<br>(index)")]
    for n, (k, t) in enumerate(steps):
        d.v(k, t, 40 + n * 200, 110, 160, 60, "key" if k == "i" else "box")
    for a, b in zip("cftk", "ftki"):
        d.e(a, b)
    d.v("src", "eldenring.wiki.gg<br>MediaWiki API", -200, 112, 180, 56, "ext")
    d.v("raw", "Bản thô theo revision<br>+ ảnh, mã băm", 20, 230, 200, 64, "db")
    d.v("dec", "decisions.jsonl<br>(giữ/bỏ + lý do)", 230, 230, 170, 50, "note")
    d.v("qd", "Qdrant: dense E5 384<br>+ sparse BM25", 760, 230, 200, 70, "db")
    d.v("pg", "PostgreSQL:<br>tài liệu, đoạn, job", 760, 330, 200, 60, "db")
    d.v("upd", "ingest update: recentchanges → chỉ dựng lại trang có revision mới", 200, 10, 560, 46, "warn")
    d.e("src", "c")
    d.e("c", "raw")
    d.e("f", "dec")
    d.e("i", "qd"); d.e("i", "pg", pts=[(860, 210), (980, 210), (980, 360)], extra="exitX=1;exitY=1;entryX=1;entryY=0.5;")
    d.e("upd", "c", extra="dashed=1;exitX=0;exitY=0.5;", pts=[(120, 33)])
    d.save()


def usecase():
    d = D("usecase")
    d.v("sys", "Hệ thống Index Beast", 220, 0, 380, 640, "group")
    d.v("web", "Người chơi web", 40, 120, 40, 70, "actor")
    d.v("dc", "Người chơi Discord", 40, 420, 40, 70, "actor")
    d.v("adm", "Quản trị viên", 720, 300, 40, 70, "actor")
    ucs = ["Đặt câu hỏi, xem câu trả lời", "Xem đoạn nguồn trích dẫn", "Chọn chế độ tìm web", "Đăng nhập, xem và xóa lịch sử",
           "Trả lời câu hỏi lại", "Chia sẻ câu trả lời", "/ask, nhắc tên bot", "/clear user (xóa ký ức)",
           "/setup, /clear all (admin server)", "Xem trace và thống kê"]
    for i, t in enumerate(ucs):
        d.v(f"u{i}", t, 260, 40 + i * 58, 300, 46, "uc")
    for i in (0, 1, 2, 3, 4, 5):
        d.e("web", f"u{i}", style="endArrow=none;html=1;strokeColor=#595959;")
    for i in (0, 4, 6, 7, 8):
        d.e("dc", f"u{i}", style="endArrow=none;html=1;strokeColor=#595959;")
    for i in (3, 9):
        d.e("adm", f"u{i}", style="endArrow=none;html=1;strokeColor=#595959;")
    d.save()


def architecture():
    d = D("architecture")
    d.v("gC", "Giao diện", 280, 0, 420, 100, "group")
    d.v("web", "Web React + Vite<br>(SSE)", 300, 30, 180, 56)
    d.v("bot", "Discord bot<br>(discord.js)", 500, 30, 180, 56)
    d.v("gB", "Backend", 260, 130, 460, 470, "group")
    d.v("caddy", "Caddy: HTTPS, web tĩnh, proxy /api", 290, 160, 400, 44)
    d.v("api", "FastAPI: xác thực, giới hạn tần suất, hạn mức", 290, 225, 400, 44)
    d.v("svc", "Dịch vụ hỏi đáp: hội thoại, khóa, thời hạn, trace", 290, 290, 400, 44)
    d.v("graph", "LangGraph ChatPipeline<br>scope → memory → <b>agent</b> → context → prompt", 290, 355, 400, 62, "key")
    d.v("gen", "Bộ sinh JSON → kiểm trích dẫn → Answer Guard<br>(song song: chọn ảnh)", 290, 440, 400, 62)
    d.v("tools", "9 công cụ của Agent", 290, 530, 190, 50, "ext")
    d.v("rr", "E5 + MiniLM-L12<br>(ONNX, CPU)", 500, 530, 190, 50, "ext")
    d.v("gD", "Lưu trữ", 760, 210, 220, 260, "group")
    d.v("rd", "Redis<br>giới hạn, hạn mức", 790, 240, 160, 60, "db")
    d.v("pg", "PostgreSQL<br>hội thoại, trace", 790, 320, 160, 60, "db")
    d.v("qd", "Qdrant<br>corpus + ký ức", 790, 400, 160, 60, "db")
    d.v("gE", "Dịch vụ ngoài", 0, 330, 220, 250, "group")
    d.v("ds", "DeepSeek API<br>deepseek-flash", 30, 360, 160, 56, "warn")
    d.v("tv", "Tavily<br>Search + Extract", 30, 440, 160, 56, "warn")
    d.v("py", "Sandbox Python<br>(tiến trình con)", 30, 515, 160, 50, "note")
    for a, b in [("web", "caddy"), ("bot", "caddy"), ("caddy", "api"), ("api", "svc"), ("svc", "graph"), ("graph", "gen")]:
        d.e(a, b)
    d.e("api", "rd", extra="endArrow=block;startArrow=block;startFill=1;")
    d.e("svc", "pg", extra="endArrow=block;startArrow=block;startFill=1;")
    d.e("graph", "ds", extra="endArrow=block;startArrow=block;startFill=1;")
    d.e("gen", "ds", pts=[(240, 471), (240, 400)], extra="endArrow=block;startArrow=block;startFill=1;")
    d.e("graph", "tools", pts=[(385, 520)], extra="exitX=0.24;exitY=1;dashed=1;")
    d.e("tools", "tv"); d.e("tools", "py", pts=[(250, 570), (250, 540)])
    d.e("tools", "rr"); d.e("rr", "qd", pts=[(740, 555), (740, 430)])
    d.save()


def deployment():
    d = D("deployment")
    d.v("net", "Internet<br>(trình duyệt, Discord)", 330, 0, 220, 56, "ext")
    d.v("vps", "VPS 4 vCPU / 8 GB · Ubuntu 24.04 · Docker Compose (mạng nội bộ)", 60, 90, 760, 380, "group")
    d.v("caddy", "caddy<br>:80, :443 (256 MB)", 360, 130, 160, 56)
    d.v("api", "api · FastAPI + Agent<br>E5, MiniLM ONNX (3 GB)", 330, 230, 220, 66, "key")
    d.v("bot", "bot · discord.js<br>(192 MB)", 80, 236, 160, 56)
    d.v("pg", "postgres (1 GB)", 120, 360, 160, 70, "db")
    d.v("qd", "qdrant (1 GB)", 360, 360, 160, 70, "db")
    d.v("rd", "redis (192 MB)", 600, 360, 160, 70, "db")
    d.v("ext", "DeepSeek, Tavily", 880, 236, 160, 56, "warn")
    d.e("net", "caddy", "HTTPS"); d.e("caddy", "api", "/api/*")
    d.e("bot", "api", "token")
    d.e("api", "pg"); d.e("api", "qd"); d.e("api", "rd"); d.e("api", "ext", "HTTPS")
    d.e("bot", "net", "Gateway Discord", pts=[(175, 28)], extra="dashed=1;exitX=0.5;exitY=0;")
    d.save()


def erd():
    d = D("erd")
    T = [
        ("documents", "id · source · title · url<br>revision_id · game_scope", 0, 0),
        ("chunks", "id · document_id<br>section · text · lang", 0, 170),
        ("users", "id · provider<br>provider_user_hash", 300, 0),
        ("auth_sessions", "id · user_id<br>token_hash · expires_at", 600, 0),
        ("conversations", "id · channel · external_ref<br>client_user_ref · user_id", 300, 170),
        ("messages", "id · conversation_id · role<br>content · sources · grounded<br>rag_trace · latency_ms<br>tokens_in · tokens_out", 600, 170),
        ("conversation_runtime", "conversation_id<br>state · revision", 300, 360),
        ("conversation_memories", "id · conversation_id<br>kind (topic/fact) · key<br>content · revision", 600, 360),
        ("feedback", "id · message_id<br>rating · reason", 900, 170),
        ("ingestion_jobs · eval_runs<br>discord_guild_channels", "(bảng phụ trợ)", 0, 360),
    ]
    for name, cols, x, y in T:
        d.v(name.split("<")[0].split(" ")[0], f"<b>{name}</b><hr>{cols}", x, y, 250, 120, "table")
    rel = "edgeStyle=orthogonalEdgeStyle;html=1;endArrow=ERmandOne;startArrow=ERmany;strokeColor=#262626;" + FONT.replace("14", "12")
    for a, b in [("chunks", "documents"), ("auth_sessions", "users"), ("conversations", "users"), ("messages", "conversations"),
                 ("conversation_memories", "conversations"), ("feedback", "messages")]:
        d.e(a, b, style=rel)
    d.e("conversation_runtime", "conversations", style=rel.replace("ERmany", "ERmandOne"))
    d.save()


def langgraph():
    d = D("langgraph")
    d.v("s", "START", 0, 40, 100, 46, "term")
    for i, k in enumerate(["scope", "memory", "agent"]):
        d.v(k, k, 160 + i * 190, 35, 140, 56, "key" if k == "agent" else "box")
    d.v("ctx", "context", 540, 190, 140, 56)
    d.v("pr", "prompt", 300, 190, 140, 56)
    d.v("e", "END", 100, 195, 100, 46, "term")
    d.v("loop", "Vòng lặp gọi công cụ<br>(ngân sách 6/12 lượt, lượt cuối chỉ finish)", 720, 30, 250, 66, "ext")
    d.e("s", "scope"); d.e("scope", "memory"); d.e("memory", "agent")
    d.e("agent", "ctx", "finish"); d.e("ctx", "pr")
    d.e("agent", "pr", "ask_user / reply", pts=[(420, 140)], extra="exitX=0.3;exitY=1;")
    d.e("pr", "e"); d.e("agent", "loop", extra="endArrow=block;startArrow=block;startFill=1;dashed=1;")
    d.save()


def turn_sequence():
    d = D("turn_sequence")
    cols = {"api": ("API", 60), "ag": ("Agent", 290), "tl": ("Công cụ", 520), "gn": ("Bộ sinh", 750), "ck": ("Bộ kiểm tra", 960)}
    for k, (t, x) in cols.items():
        d.v(k, t, x - 65, 0, 130, 640, "life")
    msgs = [("api", "ag", "câu hỏi + ngữ cảnh"), ("ag", "tl", "check_name, search_corpus (song song)"),
            ("tl", "ag", "bản xem trước"), ("ag", "tl", "open_evidence"), ("tl", "ag", "toàn văn + mã đoạn trích"),
            ("ag", "tl", "run_python (khi cần tính)"), ("tl", "ag", "kết quả in ra"),
            ("ag", "gn", "finish: bằng chứng, ý định, results"), ("gn", "ck", "JSON có trích dẫn"),
            ("ck", "gn", "sai giao thức: sinh lại tối đa 1 lần"), ("ck", "api", "câu trả lời đã kiểm, nguồn, ảnh")]
    y = 80
    for a, b, t in msgs:
        back = cols[a][1] > cols[b][1]
        d.line(cols[a][1], y, cols[b][1], y, t, extra="verticalAlign=bottom;" + ("dashed=1;" if back else ""))
        y += 50
    d.save()


ALL = [rag_pipeline, react_loop, workflow_online, clarify_sequence, offline_pipeline, usecase, architecture,
       deployment, erd, langgraph, turn_sequence]

if __name__ == "__main__":
    for f in ALL:
        f()
        print("wrote", f.__name__)
