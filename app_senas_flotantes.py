# -*- coding: utf-8 -*-
"""
App de aprendizaje del abecedario en lenguaje de señas (estilo Duolingo).
Se abre desde app_login_registro.py:  python app_senas_flotantes.py <usuario> <uid> [nuevo]

Flujo: Bienvenida -> Mapa de niveles -> Lección (estudio + quiz) -> Nivel completado
Progreso: colección 'progreso_usuarios', documento = id del usuario,
          campo 'abecedario_nivel_N' = letras superadas del nivel N.
"""
import os, sys, math, random, re, subprocess, threading, urllib.request
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageChops
import firebase_admin
from firebase_admin import credentials, firestore

USUARIO = sys.argv[1] if len(sys.argv) > 1 else "Invitado"
UID = sys.argv[2] if len(sys.argv) > 2 else None
ES_NUEVO = len(sys.argv) > 3 and sys.argv[3] == "nuevo"

LETRAS_POR_NIVEL = 5                      # <- cambia aquí el tamaño de cada nivel
ORDEN = "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"
AQUI = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(AQUI, "cache_senas")

try:
    firebase_admin.initialize_app(credentials.Certificate(os.path.join(AQUI, "serviceAccountKey.json")))
    db = firestore.client()
except Exception as e:
    print(f"Error al conectar con Firebase: {e}")
    db = None

# ---------------- Paleta (la misma del login) ----------------
TEAL_CLARO, TEAL_MEDIO, TEAL_PROFUNDO = (20, 165, 155), (10, 122, 147), (9, 111, 134)
NARANJA, HERRUMBRE = (232, 132, 26), (200, 90, 44)
COLOR_TARJETA, COLOR_BORDE_TARJETA = "#26C6DA", "#0A5F73"
COLOR_TEXTO_TITULO = COLOR_TEXTO_SECUNDARIO = "#0A5F73"
COLOR_TEXTO_CLARO, COLOR_CREMA = "#FFFFFF", "#FFE0B0"
COLOR_BOTON, COLOR_BOTON_HOVER = "#E8821A", "#66CCCC"
VERDE, ROJO, GRIS = "#2E9E5B", "#D64545", "#6FA5B3"
FUENTE_FAMILIA = "Century Gothic"

# ---------------- Datos ----------------
D = {"senas": [], "niveles": [], "prog": [], "listo": False,
     "perfil": {"hecho": False, "nivel": None}, "preguntas": [], "avatar": None}
NIVELES_USUARIO = {"principiante": ("🌱", "Principiante"), "conocedor": ("📘", "Conocedor"), "experto": ("🏆", "Experto")}
# Preguntas de respaldo: la maestra puede cambiarlas creando la colección 'diagnostico' en Firebase
PREGUNTAS_BASE = [
    {"pregunta": '¿Qué significa LSM?', "opciones": ['Lengua de Señas Mexicana', 'Libro de Señas Modernas', 'Lenguaje Sordo Mundial'], "correcta": 0, "dificultad": 1},
    {"pregunta": '¿La lengua de señas es igual en todos los países?', "opciones": ['Sí, es universal', 'No, cada país tiene la suya', 'Solo cambia en Europa'], "correcta": 1, "dificultad": 1},
    {"pregunta": '¿Cómo se comunica principalmente una persona usuaria de la LSM?', "opciones": ['Con las manos, el rostro y el cuerpo', 'Solo con la voz', 'Solo escribiendo'], "correcta": 0, "dificultad": 1},
    {"pregunta": '¿Cómo se debe llamar a una persona sorda de forma respetuosa?', "opciones": ['Sordomudo', 'Persona sorda', 'Mudito'], "correcta": 1, "dificultad": 1},
    {"pregunta": '¿Para qué sirve el alfabeto manual?', "opciones": ['Para deletrear nombres y palabras sin seña', 'Solo para contar números', 'Para sustituir toda la lengua'], "correcta": 0, "dificultad": 2},
    {"pregunta": 'Además de las manos, ¿qué es clave al señar?', "opciones": ['La expresión facial y corporal', 'Solo la velocidad', 'La voz'], "correcta": 0, "dificultad": 2},
    {"pregunta": '¿Qué profesional facilita la comunicación entre personas sordas y oyentes?', "opciones": ['Intérprete de LSM', 'Locutor', 'Mimo'], "correcta": 0, "dificultad": 2},
    {"pregunta": '¿Cómo se llama el deletreo de palabras con el alfabeto manual?', "opciones": ['Dactilología', 'Caligrafía', 'Mímica'], "correcta": 0, "dificultad": 3},
    {"pregunta": '¿Qué es la LSM?', "opciones": ['Una lengua con gramática propia, distinta del español', 'El español escrito con las manos', 'Un código de mímica'], "correcta": 0, "dificultad": 3},
    {"pregunta": '¿Qué día se celebra internacionalmente a las lenguas de señas?', "opciones": ['23 de septiembre', '14 de febrero', '1 de enero'], "correcta": 0, "dificultad": 3},
]
IMGS = {}
E = {"tok": 0, "w": [], "refs": [], "actual": None, "job": None}
L = {}
Q = {}


def bajar_imagen(letra, url):
    try:
        ruta = os.path.join(CACHE, f"{ord(letra)}.img")
        if not os.path.exists(ruta):
            os.makedirs(CACHE, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                datos = r.read()
            with open(ruta, "wb") as f:
                f.write(datos)
        img = Image.open(ruta).convert("RGB")
    except Exception as e:
        print(f"No se pudo cargar la imagen de {letra}: {e}")
        img = Image.new("RGB", (300, 300), "#EEEEEE")
        ImageDraw.Draw(img).text((140, 140), letra, fill="#0A5F73")
    IMGS[letra] = img


def cargar_datos():
    try:
        res = {}
        for d in db.collection("senas").where("categoriaId", "==", "abecedario").get():
            x = d.to_dict()
            m = re.search(r"letra\s+(\S+)", x.get("nombre", ""), re.I)   # "Letra L " -> "L"
            if m:
                res[m.group(1).upper()] = x.get("imagenUrl", "")
        senas = [(l, res[l]) for l in ORDEN if l in res]
        niveles = [senas[i:i + LETRAS_POR_NIVEL] for i in range(0, len(senas), LETRAS_POR_NIVEL)]
        prog = [0] * len(niveles)
        datos = {}
        if UID:
            ref = db.collection("progreso_usuarios").document(UID)
            snap = ref.get()
            datos = snap.to_dict() if snap.exists else {}
            for i, n in enumerate(niveles):
                prog[i] = max(0, min(len(n), int(datos.get(f"abecedario_nivel_{i + 1}", 0))))
            if not snap.exists:
                ref.set({f"abecedario_nivel_{i + 1}": 0 for i in range(len(niveles))})
        pregs = []
        for d in db.collection("diagnostico").get():          # opcional: si no existe, se usan las de respaldo
            x = d.to_dict()
            if x.get("pregunta") and len(x.get("opciones", [])) >= 2:
                pregs.append(x)
        pregs.sort(key=lambda q: int(q.get("dificultad", 1)))
        D["perfil"] = {"hecho": bool(datos.get("diagnostico_hecho")), "nivel": datos.get("nivel_usuario")}
        D["preguntas"] = pregs or PREGUNTAS_BASE
        if UID:                                               # avatar guardado en usuarios/{UID}.avatar
            D["avatar"] = (db.collection("usuarios").document(UID).get().to_dict() or {}).get("avatar")
        avatares_en_linea()
        D.update(senas=senas, niveles=niveles, prog=prog, listo=True)
        for l, u in senas:
            threading.Thread(target=bajar_imagen, args=(l, u), daemon=True).start()
    except Exception as e:
        print(e)
        D["error"] = str(e)


def guardar(nivel):
    if not (UID and db):
        return
    campo, val = f"abecedario_nivel_{nivel + 1}", D["prog"][nivel]
    def tarea():
        try:
            db.collection("progreso_usuarios").document(UID).set({campo: val}, merge=True)
        except Exception as e:
            print(f"No se pudo guardar el progreso: {e}")
    threading.Thread(target=tarea, daemon=True).start()


# ---------------- Ventana, fondo y widgets (estilo del login) ----------------
ventana = tk.Tk()
ventana.title("Lenguaje de Señas - Aprende el abecedario")
try:
    ventana.state("zoomed")
except Exception:
    ventana.attributes("-fullscreen", True)
ventana.bind("<Escape>", lambda e: ventana.attributes("-fullscreen", False))
ventana.configure(bg="#0A7A93")
lienzo = tk.Canvas(ventana, bg="#0A7A93", highlightthickness=0, bd=0)
lienzo.pack(fill="both", expand=True)


def mezcla(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def generar_degradado(ancho, alto):
    gw, gh = 96, 60
    pq = Image.new("RGB", (gw, gh))
    px = pq.load()
    for j in range(gh):
        v = j / (gh - 1)
        for i in range(gw):
            u = i / (gw - 1)
            t = u * 0.35 + v * 0.65
            base = mezcla(TEAL_CLARO, TEAL_MEDIO, t / 0.5) if t < 0.5 else mezcla(TEAL_MEDIO, TEAL_PROFUNDO, (t - 0.5) / 0.5)
            w = max(0.0, 1.0 - math.hypot((1 - u) / 0.75, (1 - v) / 0.60)) ** 1.3
            px[i, j] = mezcla(base, mezcla(HERRUMBRE, NARANJA, w * 1.4), w * 1.25)
    return pq.resize((max(1, ancho), max(1, alto)), Image.Resampling.BICUBIC)


fondo_tk = None
item_fondo = lienzo.create_image(0, 0, anchor="nw", tags="bg")


class BotonRedondeado(tk.Canvas):
    def __init__(self, parent, texto, comando, ancho=220, alto=44, tam=11, color=COLOR_BOTON,
                 color_hover=COLOR_BOTON_HOVER, color_press=COLOR_BOTON_HOVER,
                 color_borde="#FFC27A", color_sombra="#E6D5BF", color_brillo="#FFD9A3", bg_padre=COLOR_TARJETA):
        super().__init__(parent, width=ancho, height=alto, bg=bg_padre, highlightthickness=0, bd=0, cursor="hand2")
        self.ancho, self.alto, self.comando = ancho, alto, comando
        self.color, self.color_hover, self.color_press = color, color_hover, color_press
        self._rect(2, 4, ancho - 2, alto - 1, 18, fill=color_sombra, outline="")
        self.cuerpo = self._rect(2, 2, ancho - 2, alto - 4, 18, fill=color, outline=color_borde, width=1)
        self.create_line(22, 5, ancho - 22, 5, fill=color_brillo, width=1)
        self.create_text(ancho / 2, (alto - 2) / 2, text=texto, fill="white",
                         font=tkfont.Font(family=FUENTE_FAMILIA, size=tam, weight="bold"))
        self.bind("<Enter>", lambda e: self.itemconfig(self.cuerpo, fill=self.color_hover))
        self.bind("<Leave>", lambda e: self.itemconfig(self.cuerpo, fill=self.color))
        self.bind("<ButtonPress-1>", lambda e: self.itemconfig(self.cuerpo, fill=self.color_press))
        self.bind("<ButtonRelease-1>", self._soltar)

    def _rect(self, x1, y1, x2, y2, r, **kw):
        p = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
             x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(p, smooth=True, **kw)

    def _soltar(self, e):
        dentro = 0 <= e.x <= self.ancho and 0 <= e.y <= self.alto
        self.itemconfig(self.cuerpo, fill=self.color_hover if dentro else self.color)
        if dentro and self.comando:
            self.comando()


# ---------------- Helpers de dibujo ----------------
def dim():
    return lienzo.winfo_width(), lienzo.winfo_height()


def lim():
    E["tok"] += 1
    lienzo.delete("pantalla")
    for w in E["w"]:
        w.destroy()
    E["w"], E["refs"] = [], []


def fin():                                   # fondo y emojis siempre detrás de la pantalla
    lienzo.tag_lower("sena")
    lienzo.tag_lower("bg")


def txt(x, y, t, tam=12, color=COLOR_TEXTO_CLARO, fam=FUENTE_FAMILIA, sombra=False, **kw):
    if sombra:
        lienzo.create_text(x + 2, y + 3, text=t, fill="#064A5C", font=(fam, tam, "bold"), tags="pantalla", **kw)
    return lienzo.create_text(x, y, text=t, fill=color, font=(fam, tam, "bold"), tags="pantalla", **kw)


def clic(item, cmd):
    lienzo.tag_bind(item, "<Button-1>", lambda e: cmd())
    lienzo.tag_bind(item, "<Enter>", lambda e: lienzo.config(cursor="hand2"))
    lienzo.tag_bind(item, "<Leave>", lambda e: lienzo.config(cursor=""))


def rr(x1, y1, x2, y2, r=30, **kw):
    p = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
         x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return lienzo.create_polygon(p, smooth=True, tags="pantalla", **kw)


def tarjeta(cx, cy, w, h):
    x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    rr(x1 + 6, y1 + 12, x2 + 6, y2 + 12, fill="#06505F", outline="")
    rr(x1, y1, x2, y2, fill=COLOR_TARJETA, outline="#FFFFFF", width=4)
    rr(x1 + 10, y1 + 10, x2 - 10, y2 - 10, 24, fill="", outline="#7FE3EE", width=2)


def pildora(x, y, texto, w=190):
    rr(x, y - 18, x + w, y + 18, 18, fill=COLOR_BORDE_TARJETA, outline=COLOR_CREMA, width=2)
    txt(x + w / 2, y, texto, 11)


def btn(t, cmd, x, y, ancho=240, alto=42, bg=COLOR_TARJETA, **kw):
    b = BotonRedondeado(lienzo, t, cmd, ancho=ancho, alto=alto, bg_padre=bg, **kw)
    lienzo.create_window(x, y, window=b, tags="pantalla")
    E["w"].append(b)
    return b


def sena(letra, x, y, lado):
    """Dibuja la imagen de la seña (espera a que termine de descargarse si hace falta)."""
    tok = E["tok"]
    rr(x - lado / 2 - 12, y - lado / 2 - 12, x + lado / 2 + 12, y + lado / 2 + 12, 20,
       fill="#FFFFFF", outline=COLOR_BORDE_TARJETA, width=2)

    def poner():
        if tok != E["tok"]:
            return
        im = IMGS.get(letra)
        if im is None:
            t = txt(x, y, "Cargando seña…", 12, COLOR_TEXTO_SECUNDARIO)
            ventana.after(300, lambda: (lienzo.delete(t), poner()))
            return
        c = im.copy()
        c.thumbnail((lado, lado))
        ph = ImageTk.PhotoImage(c)
        E["refs"].append(ph)
        lienzo.create_image(x, y, image=ph, tags="pantalla")
    poner()


# ---------------- Pantalla 1: Bienvenida ----------------
def cerrar_sesion():
    subprocess.Popen([sys.executable, os.path.join(AQUI, "app_login_registro.py")])
    ventana.destroy()


def bienvenida():
    E["actual"] = bienvenida
    lim()
    W, H = dim()
    cx, cy = W / 2, H / 2
    txt(cx, cy - 235, f"¡Bienvenido, {USUARIO}!" if ES_NUEVO else f"¡Hola de nuevo, {USUARIO}!", 34, sombra=True)
    txt(cx, cy - 195, "Aprende, practica y conéctate con la seña", 12, COLOR_CREMA)
    tarjeta(cx, cy + 5, 560, 330)
    lienzo.create_oval(cx - 58, cy - 148, cx + 58, cy - 32, fill="#FFFFFF", outline=COLOR_BOTON, width=5, tags="pantalla")
    if D["avatar"] in AV_IMGS:
        lienzo.create_image(cx, cy - 90, image=foto_avatar(D["avatar"], 104), tags="pantalla")
    else:
        txt(cx, cy - 90, "🤟", 54, fam="Segoe UI Emoji")
    txt(cx, cy - 5, "Aprenderás el abecedario del lenguaje de señas,\nletra por letra. Completa niveles, practica con retos\ny sube de nivel a tu ritmo.",
        11, COLOR_TEXTO_SECUNDARIO, justify="center")
    st = txt(cx, H - 35, "Cargando tu progreso…", 10, COLOR_CREMA)

    def empezar():
        if D["listo"]:
            ir_a_inicio()
        else:
            lienzo.itemconfig(st, text="Cargando datos, espera un momento…")

    btn("Empezar" if ES_NUEVO else "Continuar", empezar, cx, cy + 105)
    sal = txt(cx, cy + 215, "Cerrar sesión", 10, COLOR_CREMA)
    clic(sal, cerrar_sesion)

    tok = E["tok"]
    def vigilar():
        if tok != E["tok"]:
            return
        if D["listo"]:
            lienzo.itemconfig(st, text="✔ Listo para empezar")
        elif "error" in D:
            lienzo.itemconfig(st, text="⚠️ Error de conexión con Firebase")
        else:
            ventana.after(300, vigilar)
    vigilar()
    fin()


# ---------------- Pantalla 2: Mapa de niveles ----------------
def desbloqueado(i):
    return i == 0 or D["prog"][i - 1] >= len(D["niveles"][i - 1])


def mapa():
    E["actual"] = mapa
    lim()
    W, H = dim()
    cx = W / 2
    N, hechas, total = len(D["niveles"]), sum(D["prog"]), len(D["senas"])
    txt(cx, 58, "Abecedario", 34, sombra=True)
    txt(cx, 100, f"{hechas} de {total} letras aprendidas", 12, COLOR_CREMA)
    lienzo.create_line(cx - 200, 135, cx + 200, 135, width=14, capstyle="round", fill=COLOR_BORDE_TARJETA, tags="pantalla")
    if hechas:
        lienzo.create_line(cx - 200, 135, cx - 200 + 400 * hechas / total, 135, width=14, capstyle="round",
                           fill=COLOR_BOTON, tags="pantalla")
    pildora(55, 34, USUARIO, 190)
    if D["avatar"] in AV_IMGS:
        lienzo.create_image(52, 34, image=foto_avatar(D["avatar"], 56), tags=("pantalla", "miav"))
        lienzo.create_oval(24, 6, 80, 62, outline="white", width=3, tags=("pantalla", "miav"))
        clic("miav", lambda: avatar_seleccion(mapa))
    pildora(W - 230, 34, f"⭐ {hechas}/{total} letras", 200)

    if N:
        gap = min(170, (W - 240) / max(1, N - 1))
        x0 = cx - gap * (N - 1) / 2
        pts = [(x0 + i * gap, H / 2 + (-45 if i % 2 else 45)) for i in range(N)]
        actual = next((i for i in range(N) if D["prog"][i] < len(D["niveles"][i])), None)
        for a, b in zip(pts, pts[1:]):
            lienzo.create_line(*a, *b, width=6, fill=COLOR_CREMA, dash=(10, 8), tags="pantalla")
        for i, (x, y) in enumerate(pts):
            niv, p, tag = D["niveles"][i], D["prog"][i], f"n{i}"
            n = len(niv)
            libre = desbloqueado(i)
            col, sim = (COLOR_TARJETA, "✓") if p >= n else ((COLOR_BOTON, "★") if libre else (GRIS, "🔒"))
            lienzo.create_oval(x - 48 + 5, y - 48 + 9, x + 48 + 5, y + 48 + 9, fill="#06505F", outline="", tags="pantalla")
            if i == actual:
                lienzo.create_oval(x - 66, y - 66, x + 66, y + 66, outline=COLOR_CREMA, width=4, tags=("pantalla", "pulso"))
            lienzo.create_oval(x - 48, y - 48, x + 48, y + 48, fill=col, outline="white", width=5, tags=("pantalla", tag))
            if 0 < p < n:
                lienzo.create_arc(x - 54, y - 54, x + 54, y + 54, start=90, extent=-360 * p / n, style="arc",
                                  width=6, outline="white", tags="pantalla")
            lienzo.create_text(x, y, text=sim, fill="white", font=("Segoe UI Emoji", 26, "bold"), tags=("pantalla", tag))
            txt(x, y + 78, f"Nivel {i + 1}", 13, sombra=True)
            txt(x, y + 100, f"{niv[0][0]} – {niv[-1][0]}   ({p}/{n})", 9, COLOR_CREMA)
            if i == actual:
                txt(x, y - 75, "¡Sigue aquí!", 11, COLOR_CREMA)
            if libre:
                clic(tag, lambda i=i: iniciar_nivel(i))
    btn("Volver", bienvenida, cx, H - 60, ancho=160, alto=40, bg="#0A7A93")
    fin()


# ---------------- Pantalla 3: Lección (estudio + quiz) ----------------
def iniciar_nivel(i):
    niv, p = D["niveles"][i], D["prog"][i]
    repaso = p >= len(niv)
    resto = niv if repaso else niv[p:]
    L.clear()
    L.update(i=i, resto=resto, n=len(resto), fase="estudio", k=0, ok=0, resp=None, opc=[],
             cola=random.sample(resto, len(resto)), repaso=repaso)
    leccion()


def opciones(letra):
    pool = [l for niv in D["niveles"][:L["i"] + 1] for l, _ in niv if l != letra]
    if len(pool) < 3:
        pool = [l for l, _ in D["senas"] if l != letra]
    o = random.sample(pool, min(3, len(pool))) + [letra]
    random.shuffle(o)
    return o


def leccion():
    E["actual"] = leccion
    lim()
    W, H = dim()
    cx = W / 2
    x = txt(45, 45, "✕", 20)
    clic(x, mapa)
    hecho = L["k"] if L["fase"] == "estudio" else L["n"] + L["ok"]
    lienzo.create_line(100, 45, W - 100, 45, width=16, capstyle="round", fill=COLOR_BORDE_TARJETA, tags="pantalla")
    if hecho:
        lienzo.create_line(100, 45, 100 + (W - 200) * hecho / (2 * L["n"]), 45, width=16, capstyle="round",
                           fill=COLOR_BOTON, tags="pantalla")
    tarjeta(cx, (85 + H - 40) / 2, min(700, W - 80), H - 125)

    if L["fase"] == "estudio":
        letra = L["resto"][L["k"]][0]
        lado = int(min(300, H * 0.36))
        txt(cx, 120, "Aprende esta seña", 16, COLOR_TEXTO_SECUNDARIO)
        sena(letra, cx, 162 + lado / 2, lado)
        by = 162 + lado + 62
        txt(cx - 40, by, "Letra", 24, COLOR_TEXTO_TITULO, anchor="e")
        lienzo.create_oval(cx - 31, by - 36, cx + 41, by + 36, fill=COLOR_BOTON, outline="white", width=4, tags="pantalla")
        txt(cx + 5, by, letra, 34)
        ultimo = L["k"] == L["n"] - 1
        btn("¡A practicar!" if ultimo else "Siguiente", avanzar_estudio, cx, H - 90)
    else:
        letra = L["cola"][0][0]
        lado = int(min(280, H * 0.33))
        if not L["opc"]:
            L["opc"] = opciones(letra)
        r = L["resp"]
        txt(cx, 120, "¿Qué letra es esta seña?", 16, COLOR_TEXTO_SECUNDARIO)
        sena(letra, cx, 162 + lado / 2, lado)
        y0 = 210 + lado
        for j, o in enumerate(L["opc"]):
            col, hov = COLOR_BOTON, COLOR_BOTON_HOVER
            if r and o == letra:
                col = hov = VERDE
            elif r and o == r[1]:
                col = hov = ROJO
            btn(o, lambda o=o: responder(o), cx + (-130 if j % 2 == 0 else 130), y0 + 56 * (j // 2),
                ancho=240, alto=50, tam=18, color=col, color_hover=hov, color_press=hov)
        if r:
            fondo = VERDE if r[0] else ROJO
            lienzo.create_rectangle(0, H - 110, W, H, fill=fondo, outline="", tags="pantalla")
            txt(cx - 310, H - 55, "¡Correcto! 🎉" if r[0] else f"Incorrecto. Era la letra {letra}", 16, anchor="w")
            btn("Continuar", siguiente, cx + 230, H - 55, ancho=180, bg=fondo)
    fin()


def avanzar_estudio():
    if L["k"] < L["n"] - 1:
        L["k"] += 1
    else:
        L["fase"] = "quiz"
    leccion()


def responder(o):
    if L["resp"]:
        return
    letra = L["cola"][0][0]
    L["resp"] = (o == letra, o)
    if o == letra:
        L["ok"] += 1
        if not L["repaso"]:                       # sube el progreso y se guarda en Firebase
            D["prog"][L["i"]] += 1
            guardar(L["i"])
    leccion()


def siguiente():
    ok = L["resp"][0]
    item = L["cola"].pop(0)
    if not ok:
        L["cola"].append(item)                    # la letra fallada vuelve al final
    L["resp"], L["opc"] = None, []
    leccion() if L["cola"] else completado(L["i"])


# ---------------- Pantalla 4: Nivel completado ----------------
def completado(i):
    E["actual"] = lambda: completado(i)
    lim()
    W, H = dim()
    cx, cy = W / 2, H / 2
    todo = all(p >= len(n) for p, n in zip(D["prog"], D["niveles"]))
    tarjeta(cx, cy, 560, 340)
    txt(cx, cy - 115, "🎉", 54, fam="Segoe UI Emoji")
    txt(cx, cy - 35, "¡Terminaste el abecedario!" if todo else f"¡Nivel {i + 1} completado!", 22, COLOR_TEXTO_TITULO)
    txt(cx, cy + 10, "Letras: " + " ".join(l for l, _ in D["niveles"][i]), 14, COLOR_TEXTO_SECUNDARIO)
    if i + 1 < len(D["niveles"]) and not L.get("repaso"):
        txt(cx, cy + 50, "🔓 ¡Nuevo nivel desbloqueado!", 12, COLOR_TEXTO_SECUNDARIO)
    btn("Continuar", mapa, cx, cy + 110)
    fin()
    confeti()


# ---------------- Avatares ----------------
AV_DIR = os.path.join(AQUI, "avatares")          # archivos: avatar_<nombre>.png
AV_IMGS = {}
AV_CACHE = os.path.join(AQUI, "cache_avatares")


def preparar_avatar(ruta):
    im = Image.open(ruta).convert("RGBA")
    fondo = Image.new("RGBA", im.size, "white")
    fondo.alpha_composite(im)
    rgb = fondo.convert("RGB")
    bbox = ImageChops.difference(rgb, Image.new("RGB", im.size, "white")).getbbox() or (0, 0) + im.size
    c = rgb.crop(bbox)
    lado = int(math.hypot(*c.size) * 1.03)        # cabe completo dentro del círculo
    cuadro = Image.new("RGB", (lado, lado), "white")
    cuadro.paste(c, ((lado - c.width) // 2, (lado - c.height) // 2))
    return cuadro


def foto_avatar(a, tam):
    im = AV_IMGS[a].resize((tam, tam), Image.Resampling.LANCZOS).convert("RGBA")
    m = Image.new("L", (tam * 4, tam * 4), 0)
    ImageDraw.Draw(m).ellipse((0, 0, tam * 4 - 1, tam * 4 - 1), fill=255)
    im.putalpha(m.resize((tam, tam), Image.Resampling.LANCZOS))
    ph = ImageTk.PhotoImage(im)
    E["refs"].append(ph)
    return ph


if os.path.isdir(AV_DIR):
    for f in sorted(os.listdir(AV_DIR)):
        m = re.match(r"avatar_(.+)\.png$", f, re.I)
        if m:
            try:
                AV_IMGS[m.group(1).lower()] = preparar_avatar(os.path.join(AV_DIR, f))
            except Exception as e:
                print(f"No se pudo cargar {f}: {e}")


def avatares_en_linea():
    """Lee la colección 'avatares' (nombre, imagenUrl) de Firebase y descarga las imágenes.
    Si no hay internet usa la copia guardada; los avatares de la carpeta local siempre quedan de respaldo."""
    try:
        docs = db.collection("avatares").get()
    except Exception as e:
        print(f"No se pudo leer la colección avatares: {e}")
        return
    os.makedirs(AV_CACHE, exist_ok=True)
    for d in docs:
        x = {str(k).strip(): v for k, v in d.to_dict().items()}      # tolera espacios en los nombres de campo
        n, u = str(x.get("nombre", "")).strip().lower(), str(x.get("imagenUrl", "")).strip()
        if not (n and u):
            continue
        ruta = os.path.join(AV_CACHE, re.sub(r"\W", "_", n) + ".img")
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                datos = r.read()
            with open(ruta, "wb") as f:
                f.write(datos)
        except Exception as e:
            print(f"No se pudo descargar el avatar {n}: {e}")
        if os.path.exists(ruta):
            try:
                AV_IMGS[n] = preparar_avatar(ruta)
            except Exception as e:
                print(f"Avatar {n} inválido: {e}")


def guardar_avatar(a):
    D["avatar"] = a
    if not (UID and db):
        return
    def tarea():
        try:
            db.collection("usuarios").document(UID).set({"avatar": a}, merge=True)
        except Exception as e:
            print(f"No se pudo guardar el avatar: {e}")
    threading.Thread(target=tarea, daemon=True).start()


def avatar_seleccion(volver, sel=None):
    ids = list(AV_IMGS)
    sel = sel or D["avatar"] or ids[0]
    E["actual"] = lambda: avatar_seleccion(volver, sel)
    lim()
    W, H = dim()
    cx, cy = W / 2, H / 2
    cols = min(3, len(ids))
    filas = math.ceil(len(ids) / cols)
    ch = filas * 165 + 190
    top = cy + 25 - ch / 2
    txt(cx, top - 45, "¡Elige tu avatar!", 30, sombra=True)
    tarjeta(cx, cy + 25, cols * 160 + 100, ch)
    txt(cx, top + 38, "Así te verán en tu aventura", 11, COLOR_TEXTO_SECUNDARIO)
    for k, a in enumerate(ids):
        gx = cx + ((k % cols) - (cols - 1) / 2) * 160
        gy = top + 147 + (k // cols) * 165
        t = f"av{k}"
        lienzo.create_oval(gx - 66, gy - 66, gx + 66, gy + 66, fill="white", tags=("pantalla", t),
                           outline=COLOR_BOTON if a == sel else COLOR_BORDE_TARJETA, width=7 if a == sel else 2)
        lienzo.create_image(gx, gy, image=foto_avatar(a, 116), tags=("pantalla", t))
        txt(gx, gy + 82, a.capitalize(), 10, COLOR_TEXTO_TITULO)
        clic(t, lambda a=a: avatar_seleccion(volver, a))
    btn("Confirmar", lambda: (guardar_avatar(sel), volver()), cx, top + ch - 50)
    fin()


def inicio():                                       # nuevo usuario sin avatar -> elegir avatar -> bienvenida
    if D["listo"] and not D["avatar"] and AV_IMGS:
        avatar_seleccion(bienvenida)
    elif D["listo"] or "error" in D:
        bienvenida()
    else:
        E["actual"] = None
        lim()
        W, H = dim()
        txt(W / 2, H / 2, "Cargando…", 18)
        fin()
        ventana.after(250, inicio)


# ---------------- Prueba de nivel (diagnóstico) ----------------
def guardar_perfil(**campos):
    if not (UID and db):
        return
    def tarea():
        try:
            db.collection("progreso_usuarios").document(UID).set(campos, merge=True)
        except Exception as e:
            print(f"No se pudo guardar el perfil: {e}")
    threading.Thread(target=tarea, daemon=True).start()


def destino(nivel):                       # <- aquí se conecta cada nivel con su sección
    mapa() if nivel in (None, "principiante") else proximamente(nivel)


def ir_a_inicio():
    if not D["perfil"]["hecho"] and sum(D["prog"]) == 0:
        diag_intro()
    else:
        destino(D["perfil"]["nivel"])


def diag_intro():
    E["actual"] = diag_intro
    lim()
    W, H = dim()
    cx, cy = W / 2, H / 2
    txt(cx, cy - 215, "Prueba de conocimientos", 30, sombra=True)
    tarjeta(cx, cy, 580, 320)
    txt(cx, cy - 95, "🧠", 54, fam="Segoe UI Emoji")
    txt(cx, cy - 5, f"Antes de empezar, responde {len(D['preguntas'])} preguntas sobre\nla Lengua de Señas Mexicana (LSM).\nNo hay mala nota: solo sirve para conocer tu nivel.",
        11, COLOR_TEXTO_SECUNDARIO, justify="center")
    btn("Comenzar prueba", iniciar_diag, cx, cy + 100)
    om = txt(cx, cy + 195, "Omitir prueba", 10, COLOR_CREMA)
    clic(om, lambda: terminar_diag("principiante", None))
    fin()


def preparar_q():
    Q["ord"] = random.sample(range(len(D["preguntas"][Q["k"]]["opciones"])), len(D["preguntas"][Q["k"]]["opciones"]))


def iniciar_diag():
    Q.update(k=0, pts=0)
    preparar_q()
    diag_pregunta()


def diag_pregunta():
    E["actual"] = diag_pregunta
    lim()
    W, H = dim()
    cx, cy = W / 2, H / 2
    n, q = len(D["preguntas"]), D["preguntas"][Q["k"]]
    lienzo.create_line(100, 45, W - 100, 45, width=16, capstyle="round", fill=COLOR_BORDE_TARJETA, tags="pantalla")
    if Q["k"]:
        lienzo.create_line(100, 45, 100 + (W - 200) * Q["k"] / n, 45, width=16, capstyle="round", fill=COLOR_BOTON, tags="pantalla")
    tarjeta(cx, cy + 20, 640, 120 + 60 * len(Q["ord"]) + 120)
    top = cy + 20 - (120 + 60 * len(Q["ord"]) + 120) / 2
    txt(cx, top + 40, f"Pregunta {Q['k'] + 1} de {n}", 10, COLOR_TEXTO_SECUNDARIO)
    txt(cx, top + 95, q["pregunta"], 16, COLOR_TEXTO_TITULO, width=540, justify="center")
    for j, i in enumerate(Q["ord"]):
        btn(q["opciones"][i], lambda i=i: responder_diag(i), cx, top + 175 + 60 * j, ancho=520, alto=48)
    fin()


def responder_diag(i):
    if i == int(D["preguntas"][Q["k"]].get("correcta", 0)):
        Q["pts"] += 1
    Q["k"] += 1
    n = len(D["preguntas"])
    if Q["k"] < n:
        preparar_q()
        diag_pregunta()
    else:
        pct = Q["pts"] / n                # <40% principiante, <75% conocedor, resto experto
        terminar_diag("principiante" if pct < 0.4 else "conocedor" if pct < 0.75 else "experto", Q["pts"])


def terminar_diag(nivel, pts):
    D["perfil"] = {"hecho": True, "nivel": nivel}
    campos = {"diagnostico_hecho": True, "nivel_usuario": nivel}
    if pts is not None:
        campos["diagnostico_puntaje"] = pts
    guardar_perfil(**campos)
    diag_resultado(nivel, pts)


def diag_resultado(nivel, pts):
    E["actual"] = lambda: diag_resultado(nivel, pts)
    lim()
    W, H = dim()
    cx, cy = W / 2, H / 2
    ico, nom = NIVELES_USUARIO[nivel]
    tarjeta(cx, cy, 580, 340)
    txt(cx, cy - 115, ico, 54, fam="Segoe UI Emoji")
    txt(cx, cy - 40, f"Tu nivel: {nom}", 26, COLOR_TEXTO_TITULO)
    txt(cx, cy + 10, f"Acertaste {pts} de {len(D['preguntas'])}" if pts is not None else "Prueba omitida", 13, COLOR_TEXTO_SECUNDARIO)
    btn("Continuar", lambda: destino(nivel), cx, cy + 110)
    fin()
    if pts:
        confeti()


def proximamente(nivel):
    E["actual"] = lambda: proximamente(nivel)
    lim()
    W, H = dim()
    cx, cy = W / 2, H / 2
    ico, nom = NIVELES_USUARIO[nivel]
    tarjeta(cx, cy, 580, 340)
    txt(cx, cy - 110, ico, 54, fam="Segoe UI Emoji")
    txt(cx, cy - 35, f"Nivel {nom}", 26, COLOR_TEXTO_TITULO)
    txt(cx, cy + 20, "Esta sección está en construcción 🚧\nMientras tanto, practica con el abecedario.", 12,
        COLOR_TEXTO_SECUNDARIO, justify="center")
    btn("Ir al abecedario", mapa, cx, cy + 105)
    fin()


# ---------------- Emojis flotantes (igual que el login) ----------------
EMOJIS = ["🤟", "✌️", "☝️", "🖐️", "👌", "👏", "👍", "👋"]


class SenaFlotante:
    def __init__(self, canvas, ancho, alto):
        self.canvas = canvas
        self.reiniciar(ancho, alto, True)
        self.tam = random.choice([26, 32, 40, 48])
        self.item = canvas.create_text(self.x, self.y, text=self.emoji, fill="white",
                                       font=("Segoe UI Emoji", self.tam), tags="sena")

    def reiniciar(self, ancho, alto, inicial=False):
        self.x0 = random.uniform(0, ancho)
        self.y = random.uniform(0, alto) if inicial else alto + random.uniform(20, 120)
        self.vel, self.amp = random.uniform(0.4, 1.3), random.uniform(15, 45)
        self.freq, self.fase = random.uniform(0.015, 0.04), random.uniform(0, math.tau)
        self.t, self.x = random.uniform(0, 1000), self.x0
        self.emoji = random.choice(EMOJIS)

    def actualizar(self, ancho, alto):
        self.t += 1
        self.y -= self.vel
        self.x = self.x0 + self.amp * math.sin(self.t * self.freq + self.fase)
        if self.y < -80:
            self.reiniciar(ancho, alto)
            self.canvas.itemconfig(self.item, text=self.emoji)
        self.canvas.coords(self.item, self.x, self.y)


senas_flot, ultimo_tam = [], (0, 0)
CONF = []


def confeti():
    W, H = dim()
    for _ in range(80):
        x, y = random.uniform(0, W), random.uniform(-H * 0.6, 0)
        c = random.choice(["#FFC27A", "#E8821A", "#FFFFFF", "#66CCCC", "#FFE0B0", "#2E9E5B"])
        it = lienzo.create_rectangle(x, y, x + random.randint(6, 12), y + random.randint(8, 16), fill=c, outline="", tags="pantalla")
        CONF.append([it, random.uniform(2, 5), random.uniform(-1.5, 1.5)])


def animar():
    ancho, alto = dim()
    if ancho > 50 and alto > 50:
        if not senas_flot:
            senas_flot.extend(SenaFlotante(lienzo, ancho, alto) for _ in range(45))
            fin()
        for s in senas_flot:
            s.actualizar(ancho, alto)
        E["t"] = E.get("t", 0) + 1
        lienzo.itemconfig("pulso", width=3 + 3 * abs(math.sin(E["t"] * 0.08)))
        for c in CONF[:]:
            co = lienzo.coords(c[0])
            if not co or co[1] > alto:
                lienzo.delete(c[0])
                CONF.remove(c)
            else:
                lienzo.move(c[0], c[2], c[1])
    ventana.after(33, animar)


def al_redimensionar(e):
    global fondo_tk, ultimo_tam
    if (e.width, e.height) == ultimo_tam:
        return
    ultimo_tam = (e.width, e.height)
    fondo_tk = ImageTk.PhotoImage(generar_degradado(e.width, e.height))
    lienzo.itemconfig(item_fondo, image=fondo_tk)
    if E["job"]:
        ventana.after_cancel(E["job"])
    E["job"] = ventana.after(150, lambda: E["actual"] and E["actual"]())


lienzo.bind("<Configure>", al_redimensionar)
if db:
    threading.Thread(target=cargar_datos, daemon=True).start()
else:
    D["error"] = "sin conexión"
ventana.after(250, inicio)
ventana.after(300, animar)
ventana.mainloop()