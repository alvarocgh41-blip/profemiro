"""
ProfeMiro v3 — Sistema de Exámenes Inteligente
"""

import streamlit as st
import json, random, string, csv, io, base64, os
from openai import OpenAI
import mysql.connector

def gs(key, default=None):  return st.session_state.get(key, default)
def ss(key, val):           st.session_state[key] = val

def ir(pagina):
    """Navegación directa — UN solo rerun, no dos."""
    st.session_state["page"] = pagina
    st.rerun()

# ════════════════════════════════════════════════════════════════════
#  BLOQUE TEMPRANO — operaciones BD + logout antes de set_page_config
# ════════════════════════════════════════════════════════════════════

if "_do_logout" in st.session_state:
    st.session_state.pop("_do_logout")
    for k in ["profe_id","sala_activa_id","nombre_sala","profe_nombre",
              "resultados_quiz_id","resultados_quiz_titulo"]:
        st.session_state.pop(k, None)
    st.session_state["page"] = "login"
    st.rerun()

if "_accion_bd" in st.session_state:
    import mysql.connector as _mc
    _accion   = st.session_state.pop("_accion_bd")
    _profe_id = st.session_state.get("profe_id")
    _sala_id  = st.session_state.get("sala_activa_id")
    _sala_nom = st.session_state.get("nombre_sala","")
    try:
        _db = _mc.connect(
            host=os.environ.get("DB_HOST","localhost"),
            port=int(os.environ.get("DB_PORT",3306)),
            user=os.environ.get("DB_USER","root"),
            password=os.environ.get("DB_PASSWORD","root"),
            database=os.environ.get("DB_NAME","sistema_examenes"),
        )
        _cur = _db.cursor()

        if _accion["tipo"] == "cerrar_sala":
            _cur.execute("UPDATE salas_activas SET estado='finalizado' WHERE nombre_sala=%s",(_sala_nom,))
            _db.commit(); st.session_state["_ok_msg"] = "Sala cerrada."

        elif _accion["tipo"] == "lanzar_quiz":
            _cur.execute(
                "INSERT INTO salas_activas (nombre_sala,id_quiz_activo,estado) "
                "VALUES (%s,%s,'en_progreso') "
                "ON DUPLICATE KEY UPDATE id_quiz_activo=%s, estado='en_progreso'",
                (_sala_nom, _accion["id_quiz"], _accion["id_quiz"])
            )
            _db.commit(); st.session_state["_ok_msg"] = "Examen lanzado."

        elif _accion["tipo"] == "crear_sala":
            _nuevo = _accion["nombre"].strip().upper()
            _cur.execute("SELECT nombre_sala FROM profesores WHERE nombre_sala=%s",(_nuevo,))
            if _cur.fetchone():
                st.session_state["_error_msg"] = f"El codigo '{_nuevo}' ya está en uso."
            else:
                _cur.execute("INSERT INTO salas_profesor (id_profesor,nombre_sala) VALUES (%s,%s)",
                             (_profe_id,_nuevo))
                _db.commit()
                st.session_state["nombre_sala"] = _nuevo
                st.session_state["_ok_msg"] = f"Sala '{_nuevo}' creada. Ahora estás en esa sala."

        elif _accion["tipo"] == "cambiar_sala":
            st.session_state["nombre_sala"] = _accion["nombre"]
            st.session_state["_ok_msg"] = f"Sala cambiada a '{_accion['nombre']}'."

        elif _accion["tipo"] == "eliminar_quiz":
            _id = _accion["id_quiz"]
            _cur.execute("UPDATE salas_activas SET id_quiz_activo=NULL, estado='finalizado' WHERE id_quiz_activo=%s",(_id,))
            _cur.execute("DELETE FROM respuestas_alumnos WHERE id_quiz=%s",(_id,))
            _cur.execute("DELETE FROM opciones WHERE id_pregunta IN (SELECT id_pregunta FROM preguntas WHERE id_quiz=%s)",(_id,))
            _cur.execute("DELETE FROM preguntas WHERE id_quiz=%s",(_id,))
            _cur.execute("DELETE FROM quizzes WHERE id_quiz=%s",(_id,))
            _db.commit(); st.session_state["_ok_msg"] = "Quiz eliminado."

        elif _accion["tipo"] == "eliminar_pregunta":
            _id_p = _accion["id_pregunta"]
            _cur.execute("DELETE FROM respuestas_alumnos WHERE id_pregunta=%s",(_id_p,))
            _cur.execute("DELETE FROM opciones WHERE id_pregunta=%s",(_id_p,))
            _cur.execute("DELETE FROM preguntas WHERE id_pregunta=%s",(_id_p,))
            _db.commit(); st.session_state["_ok_msg"] = "Pregunta eliminada."

        elif _accion["tipo"] == "editar_pregunta":
            _id_p = _accion["id_pregunta"]
            _tipo_p = _accion.get("tipo_preg")
            if _tipo_p:
                _cur.execute("UPDATE preguntas SET enunciado=%s,respuesta_modelo=%s,tipo=%s WHERE id_pregunta=%s",
                             (_accion["enunciado"],_accion["respuesta_modelo"],_tipo_p,_id_p))
            else:
                _cur.execute("UPDATE preguntas SET enunciado=%s,respuesta_modelo=%s WHERE id_pregunta=%s",
                             (_accion["enunciado"],_accion["respuesta_modelo"],_id_p))
            _cur.execute("DELETE FROM opciones WHERE id_pregunta=%s",(_id_p,))
            for _op in _accion.get("opciones",[]):
                _cur.execute("INSERT INTO opciones (id_pregunta,texto_opcion,es_correcta) VALUES (%s,%s,%s)",
                             (_id_p,_op["texto"],_op["correcta"]))
            _db.commit(); st.session_state["_ok_msg"] = "Pregunta actualizada."

        elif _accion["tipo"] == "añadir_pregunta":
            _cur.execute("INSERT INTO preguntas (id_quiz,enunciado,tipo,respuesta_modelo) VALUES (%s,%s,%s,%s)",
                         (_accion["id_quiz"],_accion["enunciado"],_accion["tipo_preg"],_accion["respuesta_modelo"]))
            _id_preg = _cur.lastrowid
            for _op in _accion.get("opciones",[]):
                _cur.execute("INSERT INTO opciones (id_pregunta,texto_opcion,es_correcta) VALUES (%s,%s,%s)",
                             (_id_preg,_op["texto"],_op["correcta"]))
            _db.commit(); st.session_state["_ok_msg"] = "Pregunta añadida."

        elif _accion["tipo"] == "renombrar_seccion":
            _vieja = _accion["seccion_vieja"]
            _nueva = _accion["seccion_nueva"].strip()
            if _nueva:
                _cur.execute("UPDATE quizzes SET seccion=%s WHERE id_profesor=%s AND seccion=%s",
                             (_nueva,_profe_id,_vieja))
                _db.commit(); st.session_state["_ok_msg"] = f"Seccion renombrada a '{_nueva}'."
            else:
                st.session_state["_error_msg"] = "El nombre no puede estar vacio."

        elif _accion["tipo"] == "eliminar_seccion":
            _cur.execute("UPDATE quizzes SET seccion=NULL WHERE id_profesor=%s AND seccion=%s",
                         (_profe_id,_accion["seccion"]))
            _db.commit()
            st.session_state["_ok_msg"] = "Seccion eliminada. Los quizzes quedan sin seccion."

        _db.close()
    except Exception as _e:
        st.session_state["_error_msg"] = f"Error en BD: {_e}"
    st.rerun()

if "_guardar_nota" in st.session_state:
    import mysql.connector as _mc2
    _gn = st.session_state.pop("_guardar_nota")
    try:
        _db2 = _mc2.connect(
            host=os.environ.get("DB_HOST","localhost"),
            port=int(os.environ.get("DB_PORT",3306)),
            user=os.environ.get("DB_USER","root"),
            password=os.environ.get("DB_PASSWORD","root"),
            database=os.environ.get("DB_NAME","sistema_examenes"),
        )
        _cur2 = _db2.cursor()
        _cur2.execute("UPDATE respuestas_alumnos SET puntuacion=%s,revisado=1 WHERE id_respuesta=%s",
                      (_gn["nota"],_gn["id"]))
        _db2.commit(); _db2.close()
        st.session_state["_nota_ok"] = f"Nota {_gn['nota']:.1f} guardada"
    except Exception as _e2:
        st.session_state["_nota_err"] = f"Error: {_e2}"
    st.rerun()

# ── Bloque temprano: generar quiz desde documento ─────────────────
# La llamada a la IA ocurre AQUÍ, antes de renderizar nada.
# Así cuando termina y hace st.rerun(), el árbol DOM parte de cero
# limpio, sin ningún widget previo que React tenga que reconciliar.
if "_doc_generar_pendiente" in st.session_state:
    _dgp = st.session_state.pop("_doc_generar_pendiente")
    try:
        from openai import OpenAI as _OAI2
        _model2  = os.environ.get("CENTRO_MODEL",   "gemma3")
        _client2 = _OAI2(api_key=os.environ.get("CENTRO_API_KEY","sin-clave"),
                         base_url=os.environ.get("CENTRO_API_URL","http://192.168.1.161:11434/v1"))
        _contenido2 = _dgp["contenido"]
        _cantidad2  = _dgp["cantidad"]
        _prompt2 = (f"Analiza el texto y genera exactamente {_cantidad2} preguntas de examen."
                    f" Combina TEST (4 opciones) y RESPUESTA CORTA.\nSOLO JSON:\n"
                    f'{{"titulo":"Titulo","preguntas":['
                    f'{{"enunciado":"...","tipo":"test","respuesta_modelo":"Opcion correcta exacta",'
                    f'"opciones":["Correcta","Incorrecta A","Incorrecta B","Incorrecta C"]}},'
                    f'{{"enunciado":"...","tipo":"corta","respuesta_modelo":"Respuesta"}}]}}'
                    f"\nTEXTO:\n{_contenido2[:7000]}")
        _chat2 = _client2.chat.completions.create(
            messages=[{"role":"system","content":"Respondes UNICAMENTE con JSON valido sin markdown."},
                      {"role":"user","content":_prompt2}],
            model=_model2, max_tokens=4096, temperature=0.5)
        import json as _json2
        _raw2 = _chat2.choices[0].message.content.strip()
        if "```" in _raw2:
            for _p2 in _raw2.split("```"):
                _p2 = _p2.strip()
                if _p2.lower().startswith("json"): _p2 = _p2[4:].strip()
                if _p2.startswith("{"): _raw2 = _p2; break
        _data2 = _json2.loads(_raw2)
        if _dgp.get("titulo_extra"): _data2["titulo"] = _dgp["titulo_extra"]
        st.session_state["doc_borrador"]    = _data2.get("preguntas", [])
        st.session_state["doc_titulo_base"] = _data2.get("titulo", "Quiz")
        st.session_state["doc_contenido"]   = _contenido2
        st.session_state["doc_seccion"]     = _dgp.get("seccion")
    except Exception as _e2:
        st.session_state["_doc_error"] = f"Error generando quiz: {_e2}"
    st.rerun()

if "_doc_accion" in st.session_state:
    _da = st.session_state.pop("_doc_accion")
    if _da["tipo"] == "eliminar":
        _borrador = st.session_state.get("doc_borrador", [])
        st.session_state["doc_borrador"] = [p for i,p in enumerate(_borrador) if i != _da["idx"]]
        st.rerun()
    elif _da["tipo"] == "guardar":
        import mysql.connector as _mcg
        try:
            _tit  = _da["titulo"] or st.session_state.get("doc_titulo_base","Quiz")
            _data = {"titulo": _tit, "preguntas": st.session_state.get("doc_borrador",[])}
            _dbg  = _mcg.connect(
                host=os.environ.get("DB_HOST","localhost"),
                port=int(os.environ.get("DB_PORT",3306)),
                user=os.environ.get("DB_USER","root"),
                password=os.environ.get("DB_PASSWORD","root"),
                database=os.environ.get("DB_NAME","sistema_examenes"),
            )
            _curg = _dbg.cursor()
            _curg.execute("INSERT INTO quizzes (titulo,id_profesor,seccion) VALUES (%s,%s,%s)",
                          (_data["titulo"], st.session_state.get("profe_id"),
                           st.session_state.get("doc_seccion") or None))
            _id_q = _curg.lastrowid
            for _p in _data["preguntas"]:
                _curg.execute("INSERT INTO preguntas (id_quiz,enunciado,tipo,respuesta_modelo) VALUES (%s,%s,%s,%s)",
                              (_id_q, _p["enunciado"], _p["tipo"], _p.get("respuesta_modelo","")))
                _id_preg = _curg.lastrowid
                if _p["tipo"] == "test":
                    _correcta_l = _p.get("respuesta_modelo","").strip().lower()
                    for _op in _p.get("opciones",[]):
                        _curg.execute("INSERT INTO opciones (id_pregunta,texto_opcion,es_correcta) VALUES (%s,%s,%s)",
                                      (_id_preg, _op, _op.strip().lower() == _correcta_l))
            _dbg.commit(); _dbg.close()
            for _k in ["doc_borrador","doc_contenido","doc_titulo_base","doc_seccion"]:
                st.session_state.pop(_k, None)
            st.session_state["_ok_msg"] = "Quiz guardado correctamente."
            st.session_state["page"] = "launcher"
        except Exception as _eg:
            st.session_state["_error_msg"] = f"Error guardando: {_eg}"
        st.rerun()
    elif _da["tipo"] == "generar_mas":
        from openai import OpenAI as _OAIgm
        st.session_state["doc_titulo_base"] = _da.get("titulo", st.session_state.get("doc_titulo_base","Quiz"))
        try:
            _model_gm  = os.environ.get("CENTRO_MODEL",   "gemma3")
            _client_gm = _OAIgm(api_key=os.environ.get("CENTRO_API_KEY","sin-clave"),
                                base_url=os.environ.get("CENTRO_API_URL","http://192.168.1.161:11434/v1"))
            _contenido_gm = _da.get("contenido","")
            _n_gm = _da.get("n", 3)
            _prompt_gm = (f"Analiza el texto y genera exactamente {_n_gm} preguntas de examen."
                          f" Combina TEST (4 opciones) y RESPUESTA CORTA.\nSOLO JSON:\n"
                          f'{{"titulo":"Titulo","preguntas":['
                          f'{{"enunciado":"...","tipo":"test","respuesta_modelo":"Opcion correcta exacta",'
                          f'"opciones":["Correcta","Incorrecta A","Incorrecta B","Incorrecta C"]}},'
                          f'{{"enunciado":"...","tipo":"corta","respuesta_modelo":"Respuesta"}}]}}'
                          f"\nTEXTO:\n{_contenido_gm[:7000]}")
            _chat_gm = _client_gm.chat.completions.create(
                messages=[{"role":"system","content":"Respondes UNICAMENTE con JSON valido sin markdown."},
                          {"role":"user","content":_prompt_gm}],
                model=_model_gm, max_tokens=4096, temperature=0.5)
            _raw_gm = _chat_gm.choices[0].message.content.strip()
            import json as _json_gm
            _raw_gm2 = _raw_gm
            if "```" in _raw_gm2:
                for _parte in _raw_gm2.split("```"):
                    _p2 = _parte.strip()
                    if _p2.lower().startswith("json"): _p2 = _p2[4:].strip()
                    if _p2.startswith("{"):
                        try: _raw_gm2 = _p2; break
                        except: pass
            _data_gm = _json_gm.loads(_raw_gm2)
            _exist_gm = {p.get("enunciado","").strip().lower() for p in st.session_state.get("doc_borrador",[])}
            _nuevas_gm = [p for p in _data_gm.get("preguntas",[])
                          if p.get("enunciado","").strip().lower() not in _exist_gm]
            st.session_state["doc_borrador"] = st.session_state.get("doc_borrador",[]) + _nuevas_gm
            st.session_state["_ok_msg"] = f"{len(_nuevas_gm)} preguntas nuevas añadidas."
        except Exception as _e_gm:
            st.session_state["_doc_error"] = f"Error generando: {_e_gm}"
        st.rerun()
    elif _da["tipo"] == "cancelar":
        for _k in ["doc_borrador","doc_contenido","doc_titulo_base","doc_seccion"]:
            st.session_state.pop(_k, None)
        st.session_state["page"] = "launcher"
        st.rerun()

if "_editar_quiz_bd" in st.session_state:
    import mysql.connector as _mc3
    _ed = st.session_state.pop("_editar_quiz_bd")
    try:
        _db3 = _mc3.connect(
            host=os.environ.get("DB_HOST","localhost"),
            port=int(os.environ.get("DB_PORT",3306)),
            user=os.environ.get("DB_USER","root"),
            password=os.environ.get("DB_PASSWORD","root"),
            database=os.environ.get("DB_NAME","sistema_examenes"),
        )
        _c3 = _db3.cursor()
        _c3.execute("UPDATE quizzes SET titulo=%s,seccion=%s WHERE id_quiz=%s",
                    (_ed["titulo"],_ed["seccion"] or None,_ed["id_quiz"]))
        _db3.commit(); _db3.close()
        st.session_state["_ok_msg"] = "Quiz actualizado."
    except Exception as _e3:
        st.session_state["_error_msg"] = f"Error: {_e3}"
    st.rerun()


# ════════════════════════════════════════════════════════════════════
#  CONFIG + ESTILOS
# ════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="ProfeMiro", page_icon="📚",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Nunito', sans-serif !important; }
.stApp { background: #f0ebff; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1.2rem 2rem 2rem 2rem !important; max-width: 1300px !important; }
.topbar { background:white; border-radius:20px; padding:12px 24px;
    display:flex; align-items:center; justify-content:space-between;
    box-shadow:0 4px 20px rgba(107,70,193,0.12); margin-bottom:28px; }
.topbar-logo { display:flex; align-items:center; gap:10px;
    font-size:1.4rem; font-weight:900; color:#4c1d95; letter-spacing:-0.5px; }
.topbar-logo span { color:#7c3aed; }
.sala-chip { background:linear-gradient(135deg,#ede9fe,#ddd6fe); color:#5b21b6;
    border-radius:30px; padding:6px 18px; font-size:0.85rem; font-weight:800;
    border:1px solid #c4b5fd; cursor:pointer; }
.card { background:white; border-radius:20px; padding:26px 30px;
    box-shadow:0 4px 20px rgba(107,70,193,0.08); margin-bottom:20px;
    border:1px solid rgba(107,70,193,0.06); }
.card-purple { background:linear-gradient(135deg,#7c3aed,#5b21b6); border-radius:20px;
    padding:26px 30px; color:white; margin-bottom:20px; box-shadow:0 8px 30px rgba(124,58,237,0.35); }
.card-blue { background:linear-gradient(135deg,#3b82f6,#1d4ed8); border-radius:20px;
    padding:26px 30px; color:white; margin-bottom:20px; box-shadow:0 8px 30px rgba(59,130,246,0.3); }
.card-green { background:linear-gradient(135deg,#10b981,#059669); border-radius:20px;
    padding:24px 28px; color:white; margin-bottom:20px; box-shadow:0 8px 30px rgba(16,185,129,0.3); }
.card-orange { background:linear-gradient(135deg,#f97316,#ea580c); border-radius:20px;
    padding:24px 28px; color:white; margin-bottom:20px; box-shadow:0 8px 30px rgba(249,115,22,0.3); }
.card-teal { background:linear-gradient(135deg,#06b6d4,#0891b2); border-radius:20px;
    padding:24px 28px; color:white; margin-bottom:20px; box-shadow:0 8px 30px rgba(6,182,212,0.3); }
.stat-box { flex:1; background:white; border-radius:16px; padding:20px;
    text-align:center; box-shadow:0 4px 16px rgba(107,70,193,0.08);
    border:1px solid rgba(107,70,193,0.06); }
.stat-num { font-size:2.2rem; font-weight:900; color:#7c3aed; line-height:1; }
.stat-lbl { font-size:0.75rem; color:#9ca3af; font-weight:700;
    text-transform:uppercase; letter-spacing:0.5px; margin-top:4px; }
.quiz-item { background:#fafafa; border-radius:14px; padding:16px 20px;
    margin-bottom:10px; border:1px solid #e5e7eb; }
.quiz-title { font-weight:800; color:#1f2937; font-size:0.95rem; }
.section-header { background:linear-gradient(135deg,#ede9fe,#ddd6fe);
    border-radius:16px; padding:14px 22px; margin:24px 0 12px 0; border-left:5px solid #7c3aed; }
.section-header h3 { color:#4c1d95; font-weight:900; margin:0; font-size:1.05rem; }
.section-header span { color:#6b7280; font-size:.8rem; font-weight:700; }
.badge { border-radius:20px; padding:4px 12px; font-size:0.75rem; font-weight:800; display:inline-block; }
.badge-green { background:#d1fae5; color:#065f46; }
.badge-gray  { background:#f3f4f6; color:#6b7280; }
.badge-ok    { background:#d1fae5; color:#065f46; }
.badge-fail  { background:#fee2e2; color:#991b1b; }
.badge-warn  { background:#fef3c7; color:#92400e; }
.stButton > button { border-radius:14px !important; font-weight:800 !important;
    font-size:0.9rem !important; transition:all 0.2s ease !important; }
.stButton > button:hover { transform:translateY(-2px) !important;
    box-shadow:0 6px 20px rgba(0,0,0,0.15) !important; }
.stButton > button[kind="primary"] {
    background:linear-gradient(135deg,#7c3aed,#5b21b6) !important; color:white !important; }
.stTextInput > div > div > input,
.stTextArea > div > div > textarea { border-radius:12px !important; border:2px solid #e5e7eb !important; }
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color:#7c3aed !important; box-shadow:0 0 0 3px rgba(124,58,237,0.1) !important; }
hr { border:none !important; border-top:2px solid #f3f4f6 !important; margin:12px 0 !important; }
.preg-wrap { background:white; border-radius:18px; padding:24px 28px; margin-bottom:18px;
    border-left:6px solid #7c3aed; box-shadow:0 4px 16px rgba(107,70,193,0.08); }
.preg-num { display:inline-block; background:linear-gradient(135deg,#7c3aed,#a78bfa);
    color:white; border-radius:50%; width:34px; height:34px; line-height:34px;
    text-align:center; font-weight:900; font-size:0.9rem; margin-bottom:10px; }
.res-row { background:#fafafa; border-radius:14px; padding:16px 20px;
    margin-bottom:12px; border:1px solid #e5e7eb; }
.sala-closed { background:#f9fafb; border:2px dashed #d1d5db; border-radius:16px;
    padding:24px; text-align:center; margin-bottom:20px; }
.join-logo { text-align:center; padding:40px 0 24px; }
.join-logo h1 { color:white; font-size:2.4rem; font-weight:900; margin:10px 0 4px; letter-spacing:-1px; }
.join-logo p { color:rgba(255,255,255,0.8); font-size:1rem; margin:0; }
.create-btn-card { background:white; border-radius:18px; padding:22px 18px;
    text-align:center; box-shadow:0 4px 16px rgba(107,70,193,0.1); border:2px solid transparent; }
.create-btn-icon { font-size:2.2rem; margin-bottom:8px; }
.create-btn-label { font-weight:900; color:#4c1d95; font-size:.95rem; }
.create-btn-sub { color:#9ca3af; font-size:.78rem; margin-top:4px; }
.sala-tag { display:inline-block; background:#f3f4f6; border-radius:20px;
    padding:5px 14px; font-size:.8rem; font-weight:800; color:#4c1d95;
    border:2px solid transparent; cursor:pointer; margin:3px; }
.sala-tag-active { background:linear-gradient(135deg,#ede9fe,#ddd6fe);
    border-color:#c4b5fd; color:#5b21b6; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  BD / GROQ / LOGO
# ════════════════════════════════════════════════════════════════════
def conectar():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST","localhost"),
        port=int(os.environ.get("DB_PORT",3306)),
        user=os.environ.get("DB_USER","root"),
        password=os.environ.get("DB_PASSWORD","root"),
        database=os.environ.get("DB_NAME","sistema_examenes"),
    )

@st.cache_resource
def get_ai_client():
    # ════════════════════════════════════════════════════
    # CONFIGURACIÓN API — rellena estos valores
    # Puedes ponerlos directamente aquí o como variables
    # de entorno (recomendado para Railway/producción).
    # ════════════════════════════════════════════════════
    API_KEY  = os.environ.get("CENTRO_API_KEY",  "sin-clave")
    BASE_URL = os.environ.get("CENTRO_API_URL",  "http://192.168.1.161:11434/v1")
    # Ejemplos de BASE_URL:
    #   OpenAI oficial:  https://api.openai.com/v1
    #   Azure OpenAI:    https://TU_RECURSO.openai.azure.com/openai/deployments/TU_DESPLIEGUE
    #   Ollama local:    http://localhost:11434/v1
    MODEL    = os.environ.get("CENTRO_MODEL",    "gemma3")
    # Ejemplos de MODEL: gpt-4o, gpt-4o-mini, llama3, mistral, etc.
    return OpenAI(api_key=API_KEY, base_url=BASE_URL), MODEL

def logo_svg(size=38):
    s = str(size)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="{s}" height="{s}">'
            f'<rect width="48" height="48" rx="12" fill="#7c3aed"/>'
            f'<rect x="8" y="14" width="14" height="20" rx="2" fill="#a78bfa" opacity="0.85"/>'
            f'<rect x="26" y="14" width="14" height="20" rx="2" fill="#a78bfa" opacity="0.85"/>'
            f'<rect x="21" y="12" width="6" height="24" rx="2" fill="#fbbf24"/>'
            f'<line x1="10" y1="20" x2="20" y2="20" stroke="white" stroke-width="1.5" stroke-linecap="round"/>'
            f'<line x1="10" y1="24" x2="20" y2="24" stroke="white" stroke-width="1.5" stroke-linecap="round"/>'
            f'<line x1="10" y1="28" x2="17" y2="28" stroke="white" stroke-width="1.2" stroke-linecap="round"/>'
            f'<line x1="28" y1="20" x2="38" y2="20" stroke="white" stroke-width="1.5" stroke-linecap="round"/>'
            f'<line x1="28" y1="24" x2="38" y2="24" stroke="white" stroke-width="1.5" stroke-linecap="round"/>'
            f'<line x1="28" y1="28" x2="35" y2="28" stroke="white" stroke-width="1.2" stroke-linecap="round"/>'
            f'<polygon points="40,4 41.2,8 45,8.2 42,10.5 43,14 40,12 37,14 38,10.5 35,8.2 38.8,8" fill="#fbbf24"/>'
            f'</svg>')

def get_salas_profe(profe_id):
    try:
        db = conectar(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT nombre_sala FROM profesores WHERE id_profesor=%s",(profe_id,))
        row = cur.fetchone()
        sala_orig = row["nombre_sala"] if row else ""
        cur.execute("SELECT nombre_sala FROM salas_profesor WHERE id_profesor=%s ORDER BY id",(profe_id,))
        extras = [r["nombre_sala"] for r in cur.fetchall()]
        db.close()
        todas = [sala_orig] if sala_orig else []
        for s in extras:
            if s not in todas: todas.append(s)
        return todas
    except:
        return [gs("nombre_sala","")]

def render_topbar_profe(nombre_sala=None, tab="launcher"):
    chip = f'<span class="sala-chip">🏫 {nombre_sala}</span>' if nombre_sala else ""
    st.markdown(f'<div class="topbar"><div class="topbar-logo">{logo_svg(38)}&nbsp;Profe<span>Miro</span></div>{chip}</div>',
                unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Launcher", use_container_width=True,
                     type="primary" if tab=="launcher" else "secondary", key="nav_launcher"):
            ir("launcher")
    with col2:
        if st.button("📚 Biblioteca", use_container_width=True,
                     type="primary" if tab=="biblioteca" else "secondary", key="nav_biblioteca"):
            ir("biblioteca")
    st.markdown("<br>", unsafe_allow_html=True)

def render_topbar(sala=None):
    chip = f'<span class="sala-chip">🏫 {sala}</span>' if sala else ""
    st.markdown(f'<div class="topbar"><div class="topbar-logo">{logo_svg(38)}&nbsp;Profe<span>Miro</span></div>{chip}</div>',
                unsafe_allow_html=True)

def _extraer_json(raw):
    raw = raw.strip()
    if "```" in raw:
        for parte in raw.split("```"):
            p = parte.strip()
            if p.lower().startswith("json"): p = p[4:].strip()
            if p.startswith("{"):
                try: return json.loads(p)
                except: pass
    if raw.startswith("{"):
        try: return json.loads(raw)
        except: pass
    inicio = raw.find("{")
    if inicio != -1:
        depth = 0
        for k in range(inicio, len(raw)):
            if raw[k] == "{": depth += 1
            elif raw[k] == "}":
                depth -= 1
                if depth == 0:
                    try: return json.loads(raw[inicio:k+1])
                    except: break
    raise ValueError(f"Sin JSON valido: {raw[:300]}")

def generar_quiz_ia(fuente, cantidad, es_documento=False):
    client, model = get_ai_client()
    base = (f"Analiza el texto y genera exactamente {cantidad} preguntas de examen."
            if es_documento else f"Genera exactamente {cantidad} preguntas sobre: \"{fuente}\".")
    prompt = (f"{base} Combina TEST (4 opciones) y RESPUESTA CORTA.\nSOLO JSON:\n"
              f'{{"titulo":"Titulo","preguntas":['
              f'{{"enunciado":"...","tipo":"test","respuesta_modelo":"Opcion correcta exacta",'
              f'"opciones":["Correcta","Incorrecta A","Incorrecta B","Incorrecta C"]}},'
              f'{{"enunciado":"...","tipo":"corta","respuesta_modelo":"Respuesta"}}]}}'
              + (f"\nTEXTO:\n{fuente[:7000]}" if es_documento else ""))
    chat = client.chat.completions.create(
        messages=[
            {"role":"system","content":"Respondes UNICAMENTE con JSON valido sin markdown."},
            {"role":"user","content":prompt}
        ],
        model=model, max_tokens=4096, temperature=0.5,
    )
    return _extraer_json(chat.choices[0].message.content.strip())

def guardar_quiz_bd(data, profe_id, seccion=None):
    db = conectar(); cur = db.cursor()
    cur.execute("INSERT INTO quizzes (titulo,id_profesor,seccion) VALUES (%s,%s,%s)",
                (data["titulo"], profe_id, seccion or None))
    id_quiz = cur.lastrowid
    for p in data.get("preguntas",[]):
        cur.execute("INSERT INTO preguntas (id_quiz,enunciado,tipo,respuesta_modelo) VALUES (%s,%s,%s,%s)",
                    (id_quiz, p["enunciado"], p["tipo"], p.get("respuesta_modelo","")))
        id_preg = cur.lastrowid
        if p["tipo"] == "test" and "opciones" in p:
            correcta_l = p.get("respuesta_modelo","").strip().lower()
            for op in p["opciones"]:
                cur.execute("INSERT INTO opciones (id_pregunta,texto_opcion,es_correcta) VALUES (%s,%s,%s)",
                            (id_preg, op, op.strip().lower() == correcta_l))
    db.commit(); db.close()
    return id_quiz

def widget_seccion(profe_id, key_prefix=""):
    # El text_input de nueva seccion SIEMPRE se renderiza (nunca dentro de if/else)
    # para mantener el arbol DOM estable y evitar removeChild.
    # Se oculta con label_visibility="collapsed" cuando no se necesita.
    try:
        db = conectar(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT DISTINCT seccion FROM quizzes WHERE id_profesor=%s AND seccion IS NOT NULL AND seccion!='' ORDER BY seccion",(profe_id,))
        secs = [r["seccion"] for r in cur.fetchall()]; db.close()
    except: secs = []
    opciones = ["Sin seccion"] + secs + ["Nueva seccion..."]
    sel = st.selectbox("Seccion del quiz", opciones, key=f"{key_prefix}_sec_sel")
    vis = "visible" if sel == "Nueva seccion..." else "collapsed"
    nueva = st.text_input("Nombre de la nueva seccion",
                          placeholder="Ej: Fisica, Quimica...",
                          key=f"{key_prefix}_sec_nueva",
                          label_visibility=vis)
    if sel == "Nueva seccion...":
        return nueva.strip() or None
    return None if sel == "Sin seccion" else sel


# ════════════════════════════════════════════════════════════════════
#  ROUTER
# ════════════════════════════════════════════════════════════════════
def main():
    page = gs("page","alumno_join")
    if gs("profe_id") and page in ("login","register","alumno_join"):
        st.session_state["page"] = "launcher"; page = "launcher"
    {
        "alumno_join": pg_alumno_join, "examen_alumno": pg_examen_alumno,
        "alumno_fin": pg_alumno_fin, "login": pg_login, "register": pg_register,
        "launcher": pg_launcher, "biblioteca": pg_biblioteca,
        "editar_quiz": pg_editar_quiz, "resultados": pg_resultados,
        "crear_quiz_ia": pg_crear_ia, "crear_quiz_doc": pg_crear_doc,
        "crear_quiz_manual": pg_crear_manual,
    }.get(page, pg_alumno_join)()


# ════════════════════════════════════════════════════════════════════
#  ALUMNO JOIN
# ════════════════════════════════════════════════════════════════════
def pg_alumno_join():
    st.markdown("""<style>.stApp{background:linear-gradient(135deg,#667eea,#764ba2)!important;}
    .block-container{max-width:520px!important;margin:0 auto!important;}</style>""", unsafe_allow_html=True)
    st.markdown(f'<div class="join-logo">{logo_svg(72)}<h1>ProfeMiro</h1><p>Sistema de examenes inteligente</p></div>',
                unsafe_allow_html=True)
    st.markdown("### Unirse al Examen")
    nombre = st.text_input("Tu nombre completo", placeholder="Ej: Ana Garcia Lopez", key="j_nombre")
    sala   = st.text_input("Codigo de sala", placeholder="Ej: SALA101", key="j_sala")
    if st.button("Entrar al Examen", use_container_width=True, type="primary", key="j_btn"):
        n = nombre.strip(); s = sala.strip().upper()
        if not n or not s:
            ss("_join_error","Rellena tu nombre y el codigo de sala.")
        else:
            try:
                db = conectar(); cur = db.cursor(dictionary=True)
                cur.execute("SELECT * FROM salas_activas WHERE nombre_sala=%s AND estado='en_progreso'",(s,))
                sala_data = cur.fetchone(); db.close()
                if not sala_data:
                    ss("_join_error","La sala no existe o ya esta cerrada.")
                else:
                    db2 = conectar(); cur2 = db2.cursor(dictionary=True)
                    cur2.execute("SELECT id_respuesta FROM respuestas_alumnos WHERE nombre_alumno=%s AND codigo_reunion=%s AND id_quiz=%s LIMIT 1",
                                 (n, s, sala_data["id_quiz_activo"]))
                    ya = cur2.fetchone(); db2.close()
                    if ya: ss("_join_error", f"{n}, ya has completado este examen.")
                    else:
                        ss("alumno_nombre",n); ss("sala",s)
                        ss("id_quiz", sala_data["id_quiz_activo"])
                        ir("examen_alumno")
            except Exception as e: ss("_join_error", f"Error: {e}")
    if gs("_join_error"): st.error(st.session_state.pop("_join_error"))
    st.markdown("---")
    if st.button("Soy profesor — Iniciar sesion", use_container_width=True, key="j_profe"):
        ir("login")

# ════════════════════════════════════════════════════════════════════
#  ALUMNO EXAMEN
# ════════════════════════════════════════════════════════════════════
def pg_examen_alumno():
    id_quiz = gs("id_quiz"); nombre = gs("alumno_nombre"); sala = gs("sala")
    if not id_quiz: ir("alumno_join"); return
    if "preguntas_examen" not in st.session_state:
        try:
            db = conectar(); cur = db.cursor(dictionary=True)
            cur.execute("SELECT * FROM preguntas WHERE id_quiz=%s",(id_quiz,))
            preguntas = cur.fetchall(); random.shuffle(preguntas)
            for p in preguntas:
                try:
                    d = json.loads(p["enunciado"]); p["texto"]=d.get("texto",p["enunciado"]); p["imagen"]=d.get("imagen","")
                except: p["texto"]=p["enunciado"]; p["imagen"]=""
                if p["tipo"]=="test":
                    cur.execute("SELECT * FROM opciones WHERE id_pregunta=%s",(p["id_pregunta"],))
                    ops=cur.fetchall(); random.shuffle(ops); p["opciones"]=ops
                else: p["opciones"]=[]
            db.close(); ss("preguntas_examen",preguntas)
        except Exception as e: st.error(f"Error cargando examen: {e}"); return
    preguntas = gs("preguntas_examen",[])
    st.markdown(f"""<div style="background:white;border-radius:20px;padding:18px 28px;
         box-shadow:0 4px 20px rgba(107,70,193,0.12);margin-bottom:28px;
         display:flex;justify-content:space-between;align-items:center;border-left:6px solid #7c3aed;">
        <div><div style="font-size:1.2rem;font-weight:900;color:#4c1d95;">Examen - Sala {sala}</div>
        <div style="color:#9ca3af;font-size:.85rem;">{len(preguntas)} preguntas</div></div>
        <div style="background:linear-gradient(135deg,#ede9fe,#ddd6fe);border-radius:30px;
             padding:8px 20px;font-weight:800;color:#5b21b6;border:1px solid #c4b5fd;">{nombre}</div></div>""",
                unsafe_allow_html=True)
    respuestas = {}
    with st.form("form_examen", clear_on_submit=False):
        for i, p in enumerate(preguntas):
            st.markdown(f'<div class="preg-wrap"><div class="preg-num">{i+1}</div>'
                        f'<div style="font-size:1.05rem;font-weight:700;color:#1f2937;margin-top:4px;">{p["texto"]}</div></div>',
                        unsafe_allow_html=True)
            if p.get("imagen"):
                try: st.image(p["imagen"], width=320)
                except: pass
            if p["tipo"]=="test":
                opts=[op["texto_opcion"] for op in p["opciones"]]
                respuestas[p["id_pregunta"]]=st.radio(f"Op{i}",opts,key=f"r_{p['id_pregunta']}",label_visibility="collapsed")
            else:
                respuestas[p["id_pregunta"]]=st.text_area(f"R{i}",key=f"r_{p['id_pregunta']}",
                    placeholder="Escribe tu respuesta...",label_visibility="collapsed",height=100)
            st.markdown("<hr>",unsafe_allow_html=True)
        enviado=st.form_submit_button("Finalizar y Enviar Examen",use_container_width=True,type="primary")
    if enviado:
        with st.spinner("Guardando respuestas..."):
            try:
                db=conectar(); cur=db.cursor(dictionary=True)
                for id_preg,valor in respuestas.items():
                    cur.execute("SELECT tipo,respuesta_modelo FROM preguntas WHERE id_pregunta=%s",(id_preg,))
                    pd=cur.fetchone()
                    if not pd: continue
                    punt=0.0; rev=0
                    if pd["tipo"]=="test":
                        if str(valor or "").strip().lower()==str(pd["respuesta_modelo"] or "").strip().lower(): punt=1.0
                        rev=1
                    cur.execute("INSERT INTO respuestas_alumnos (id_quiz,id_pregunta,nombre_alumno,codigo_reunion,contenido_respuesta,puntuacion,revisado) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                (id_quiz,id_preg,nombre,sala,valor or "",punt,rev))
                db.commit(); db.close()
                for k in ["preguntas_examen","id_quiz","sala"]: st.session_state.pop(k,None)
                ir("alumno_fin")
            except Exception as e: st.error(f"Error al guardar: {e}")

# ════════════════════════════════════════════════════════════════════
#  ALUMNO FIN
# ════════════════════════════════════════════════════════════════════
def pg_alumno_fin():
    nombre=gs("alumno_nombre","Alumno")
    st.markdown("""<style>.stApp{background:linear-gradient(135deg,#10b981,#059669)!important;}
    .block-container{max-width:520px!important;margin:0 auto!important;}</style>""",unsafe_allow_html=True)
    st.markdown(f"""<div style="margin-top:80px;"><div class="card" style="text-align:center;padding:52px 40px;">
        <div style="font-size:5rem;margin-bottom:16px;">🎉</div>
        <h2 style="color:#065f46;font-weight:900;">Examen enviado!</h2>
        <p style="color:#047857;">Buen trabajo, <strong>{nombre}</strong>.</p>
        <div style="margin-top:24px;padding:14px 24px;background:#f0fdf4;border-radius:12px;
             border:1px solid #a7f3d0;color:#065f46;font-weight:700;">Puedes cerrar esta ventana</div>
    </div></div>""",unsafe_allow_html=True)
    if st.button("Hacer otro examen", key="fin_btn"):
        for k in ["alumno_nombre","id_quiz","sala","preguntas_examen"]: st.session_state.pop(k,None)
        ir("alumno_join")


# ════════════════════════════════════════════════════════════════════
#  LOGIN / REGISTRO
# ════════════════════════════════════════════════════════════════════
def pg_login():
    st.markdown("""<style>.stApp{background:linear-gradient(135deg,#667eea,#764ba2)!important;}
    .block-container{max-width:480px!important;margin:0 auto!important;}</style>""",unsafe_allow_html=True)
    st.markdown(f'<div class="join-logo">{logo_svg(60)}<h1>ProfeMiro</h1><p>Panel del Profesor</p></div>',unsafe_allow_html=True)
    st.markdown("### Iniciar Sesion")
    email=st.text_input("Email",placeholder="tu@email.com",key="l_email")
    password=st.text_input("Contrasena",type="password",key="l_pass")
    if st.button("Iniciar Sesion",use_container_width=True,type="primary",key="l_btn"):
        if not email.strip() or not password: ss("_login_error","Rellena email y contrasena.")
        else:
            try:
                db=conectar(); cur=db.cursor(dictionary=True)
                cur.execute("SELECT * FROM profesores WHERE email=%s AND password=%s",(email.strip(),password))
                profe=cur.fetchone(); db.close()
                if profe:
                    ss("profe_id",profe["id_profesor"]); ss("nombre_sala",profe["nombre_sala"])
                    ss("profe_nombre",profe["nombre"]); ir("launcher")
                else: ss("_login_error","Email o contrasena incorrectos.")
            except Exception as e: ss("_login_error",f"Error: {e}")
    if gs("_login_error"): st.error(st.session_state.pop("_login_error"))
    st.markdown("---")
    if st.button("Crear cuenta nueva",use_container_width=True,key="l_reg"): ir("register")
    if st.button("Volver (soy alumno)",key="l_back"): ir("alumno_join")

def pg_register():
    st.markdown("""<style>.stApp{background:linear-gradient(135deg,#667eea,#764ba2)!important;}
    .block-container{max-width:480px!important;margin:0 auto!important;}</style>""",unsafe_allow_html=True)
    st.markdown(f'<div class="join-logo">{logo_svg(60)}<h1>ProfeMiro</h1><p>Crea tu cuenta</p></div>',unsafe_allow_html=True)
    nombre=st.text_input("Nombre completo",placeholder="Prof. Garcia",key="reg_n")
    email=st.text_input("Email",placeholder="tu@email.com",key="reg_e")
    password=st.text_input("Contrasena",type="password",key="reg_p")
    if st.button("Crear mi cuenta",use_container_width=True,type="primary",key="reg_btn"):
        if not (nombre.strip() and email.strip() and password): ss("_reg_error","Rellena todos los campos.")
        elif len(password)<4: ss("_reg_error","La contrasena debe tener al menos 4 caracteres.")
        else:
            try:
                sala_code="SALA_"+"".join(random.choices(string.ascii_uppercase+string.digits,k=5))
                db=conectar(); cur=db.cursor(dictionary=True)
                cur.execute("SELECT id_profesor FROM profesores WHERE email=%s",(email.strip(),))
                if cur.fetchone(): db.close(); ss("_reg_error","Este email ya esta registrado.")
                else:
                    cur.execute("INSERT INTO profesores (nombre,email,password,nombre_sala) VALUES (%s,%s,%s,%s)",
                                (nombre.strip(),email.strip(),password,sala_code))
                    db.commit(); db.close(); ss("_reg_ok",f"Cuenta creada! Tu sala es: {sala_code}")
            except Exception as e: ss("_reg_error",f"Error: {e}")
    if gs("_reg_error"): st.error(st.session_state.pop("_reg_error"))
    if gs("_reg_ok"): st.success(st.session_state.pop("_reg_ok")); st.info("Ya puedes iniciar sesion.")
    st.markdown("---")
    if st.button("Volver al login",key="reg_back"): ir("login")


# ════════════════════════════════════════════════════════════════════
#  LAUNCHER
# ════════════════════════════════════════════════════════════════════
def pg_launcher():
    profe_id=gs("profe_id"); nombre_sala=gs("nombre_sala","")
    if not profe_id: ir("login"); return
    render_topbar_profe(nombre_sala,tab="launcher")
    if gs("_error_msg"): st.error(st.session_state.pop("_error_msg"))
    if gs("_ok_msg"): st.success(st.session_state.pop("_ok_msg"))

    try:
        db=conectar(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT * FROM quizzes WHERE id_profesor=%s ORDER BY fecha_creacion DESC",(profe_id,))
        quizzes=cur.fetchall()
        cur.execute("SELECT id_quiz_activo,estado FROM salas_activas WHERE nombre_sala=%s",(nombre_sala,))
        sala_info=cur.fetchone()
        cur.execute("SELECT COUNT(DISTINCT nombre_alumno) AS t FROM respuestas_alumnos ra JOIN quizzes q ON ra.id_quiz=q.id_quiz WHERE q.id_profesor=%s",(profe_id,))
        total_alumnos=(cur.fetchone() or {}).get("t",0); db.close()
    except Exception as e: st.error(f"Error: {e}"); return

    sala_activa=bool(sala_info and sala_info["estado"]=="en_progreso")
    quiz_tit_activo=next((q["titulo"] for q in quizzes if sala_activa and q["id_quiz"]==sala_info["id_quiz_activo"]),"")

    st.markdown('<div style="font-weight:900;color:#4c1d95;font-size:1rem;margin-bottom:8px;">Mis salas</div>',unsafe_allow_html=True)
    mis_salas = get_salas_profe(profe_id)
    salas_html = ""
    for s in mis_salas:
        activa_cls = "sala-tag-active" if s == nombre_sala else ""
        salas_html += f'<span class="sala-tag {activa_cls}">{s}</span>'
    st.markdown(f'<div style="margin-bottom:10px;">{salas_html}</div>', unsafe_allow_html=True)

    col_sel, col_new, col_crear = st.columns([2, 2, 1])
    with col_sel:
        idx_sala = mis_salas.index(nombre_sala) if nombre_sala in mis_salas else 0
        sala_elegida = st.selectbox("Sala activa", mis_salas, index=idx_sala, key="l_sala_sel", label_visibility="collapsed")
        if sala_elegida != nombre_sala:
            ss("nombre_sala", sala_elegida); st.rerun()
    with col_new:
        nueva_sala_txt = st.text_input("Nueva sala", placeholder="Ej: CLASE_3A", key="l_nueva_sala", label_visibility="collapsed")
    with col_crear:
        st.markdown("<div style='margin-top:4px;'>",unsafe_allow_html=True)
        if st.button("Crear sala", key="l_crear_sala", use_container_width=True):
            cod = nueva_sala_txt.strip().upper().replace(" ","_")
            if not cod:
                ss("_error_msg","Escribe un nombre para la nueva sala.")
            elif cod in mis_salas:
                ss("_error_msg","Ya tienes una sala con ese nombre.")
            else:
                ss("_accion_bd",{"tipo":"crear_sala","nombre":cod})
            st.rerun()
        st.markdown("</div>",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    sala_html=(f'<div class="card-green" style="margin-bottom:0;padding:18px 24px;">'
               f'<div style="font-size:.95rem;font-weight:900;margin-bottom:4px;">🟢 SALA ABIERTA</div>'
               f'<div style="opacity:.95;font-size:.88rem;">Codigo: <strong>{nombre_sala}</strong> · {quiz_tit_activo}</div></div>'
               if sala_activa else
               f'<div class="sala-closed" style="margin-bottom:0;padding:18px 24px;">'
               f'<span style="font-weight:800;color:#6b7280;">Sala cerrada</span> · '
               f'<span style="color:#9ca3af;">Codigo: <strong>{nombre_sala}</strong></span></div>')
    st.markdown(f"""<div style="display:flex;gap:14px;margin-bottom:16px;align-items:stretch;">
        <div class="stat-box" style="min-width:90px;"><div class="stat-num">{len(quizzes)}</div><div class="stat-lbl">Quizzes</div></div>
        <div class="stat-box" style="min-width:90px;"><div class="stat-num">{total_alumnos}</div><div class="stat-lbl">Alumnos</div></div>
        <div style="flex:1;">{sala_html}</div></div>""",unsafe_allow_html=True)

    if st.button("Cerrar sala ahora", use_container_width=True, key="l_cerrar",
                 disabled=not sala_activa):
        ss("_accion_bd",{"tipo":"cerrar_sala"}); st.rerun()

    st.markdown("<br>",unsafe_allow_html=True)

    st.markdown('<div style="font-weight:900;color:#4c1d95;font-size:1.05rem;margin-bottom:14px;">Crear cuestionario</div>',unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    with c1:
        st.markdown('<div class="create-btn-card"><div class="create-btn-icon">🪄</div><div class="create-btn-label">Generar con IA</div><div class="create-btn-sub">Por tema libre</div></div>',unsafe_allow_html=True)
        if st.button("Usar IA",use_container_width=True,type="primary",key="l_ia"): ir("crear_quiz_ia")
    with c2:
        st.markdown('<div class="create-btn-card"><div class="create-btn-icon">📄</div><div class="create-btn-label">Desde documento</div><div class="create-btn-sub">TXT o CSV</div></div>',unsafe_allow_html=True)
        if st.button("Subir doc",use_container_width=True,key="l_doc"): ir("crear_quiz_doc")
    with c3:
        st.markdown('<div class="create-btn-card"><div class="create-btn-icon">✏️</div><div class="create-btn-label">Manual</div><div class="create-btn-sub">Pregunta a pregunta</div></div>',unsafe_allow_html=True)
        if st.button("Crear manual",use_container_width=True,key="l_man"): ir("crear_quiz_manual")

    st.markdown("<br>",unsafe_allow_html=True)

    # ── Lanzar examen — selectbox SIEMPRE presente ────────────────
    st.markdown('<div style="font-weight:900;color:#4c1d95;font-size:1.05rem;margin-bottom:12px;">Lanzar examen</div>',unsafe_allow_html=True)

    secciones_disp = sorted({q.get("seccion") or "Sin seccion" for q in quizzes}) if quizzes else []
    sec_opts = ["Todas"] + secciones_disp
    sec_sel_l = gs("launcher_sec_filtro","Todas")
    if sec_sel_l not in sec_opts: sec_sel_l = "Todas"
    sel_l = st.selectbox("Filtrar seccion", sec_opts, index=sec_opts.index(sec_sel_l),
                         key="launcher_sec_sel", label_visibility="collapsed")
    if sel_l != sec_sel_l:
        ss("launcher_sec_filtro", sel_l); st.rerun()

    if not quizzes:
        st.markdown('<div style="text-align:center;padding:30px;color:#9ca3af;background:white;'
                    'border-radius:16px;border:1px solid #e5e7eb;">'
                    '<div style="font-size:2.5rem;">📭</div>'
                    '<div style="font-weight:700;">Crea tu primer cuestionario</div></div>',
                    unsafe_allow_html=True)
    else:
        quizzes_f = quizzes if sec_sel_l=="Todas" else [q for q in quizzes if (q.get("seccion") or "Sin seccion")==sec_sel_l]
        for quiz in quizzes_f:
            es_activo = sala_activa and sala_info["id_quiz_activo"]==quiz["id_quiz"]
            badge = ('<span class="badge badge-green">● Activo</span>' if es_activo else '<span class="badge badge-gray">Inactivo</span>')
            st.markdown(f'<div class="quiz-item"><div class="quiz-title">{quiz["titulo"]}</div><div style="margin-top:4px;">{badge}</div></div>',unsafe_allow_html=True)
            lbl_lanzar = "● Ya activo" if es_activo else "🚀 Lanzar"
            if st.button(lbl_lanzar, key=f"l_lanzar_{quiz['id_quiz']}", use_container_width=True,
                         type="primary", disabled=es_activo):
                ss("_accion_bd",{"tipo":"lanzar_quiz","id_quiz":quiz["id_quiz"]}); st.rerun()
            st.markdown("<hr>",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    if st.button("Cerrar sesion",use_container_width=True,key="l_logout"): ss("_do_logout",True)


# ════════════════════════════════════════════════════════════════════
#  BIBLIOTECA
# ════════════════════════════════════════════════════════════════════
def pg_biblioteca():
    profe_id=gs("profe_id"); nombre_sala=gs("nombre_sala","")
    if not profe_id: ir("login"); return
    render_topbar_profe(nombre_sala, tab="biblioteca")
    if gs("_error_msg"): st.error(st.session_state.pop("_error_msg"))
    if gs("_ok_msg"):    st.success(st.session_state.pop("_ok_msg"))

    try:
        db=conectar(); cur=db.cursor(dictionary=True)
        cur.execute(
            "SELECT q.*,"
            "(SELECT COUNT(*) FROM preguntas p WHERE p.id_quiz=q.id_quiz) AS n_preguntas,"
            "(SELECT COUNT(DISTINCT ra.nombre_alumno) FROM respuestas_alumnos ra WHERE ra.id_quiz=q.id_quiz) AS n_alumnos "
            "FROM quizzes q WHERE q.id_profesor=%s ORDER BY COALESCE(q.seccion,'ZZZZ'),q.fecha_creacion DESC",
            (profe_id,)
        )
        quizzes=cur.fetchall(); db.close()
    except Exception as e: st.error(f"Error: {e}"); return

    total_q=len(quizzes)
    total_preg=sum(q.get("n_preguntas",0) for q in quizzes)
    total_al=sum(q.get("n_alumnos",0) for q in quizzes)
    secciones=sorted({q.get("seccion") or "Sin seccion" for q in quizzes})
    n_secs=len([s for s in secciones if s!="Sin seccion"])

    st.markdown(f"""<div style="display:flex;gap:14px;margin-bottom:24px;">
        <div class="stat-box"><div class="stat-num">{total_q}</div><div class="stat-lbl">Quizzes</div></div>
        <div class="stat-box"><div class="stat-num">{total_preg}</div><div class="stat-lbl">Preguntas</div></div>
        <div class="stat-box"><div class="stat-num">{total_al}</div><div class="stat-lbl">Respuestas</div></div>
        <div class="stat-box"><div class="stat-num">{n_secs}</div><div class="stat-lbl">Secciones</div></div>
    </div>""", unsafe_allow_html=True)

    if not quizzes:
        st.markdown('<div style="text-align:center;padding:60px;color:#9ca3af;background:white;border-radius:20px;">📭 Sin cuestionarios aun. Crea el primero desde el Launcher.</div>',unsafe_allow_html=True); return

    sec_opciones=["Todas"]+list(secciones)
    sec_sel_b=gs("bib_sec_filtro","Todas")
    if sec_sel_b not in sec_opciones: sec_sel_b="Todas"
    sel=st.selectbox("Filtrar seccion",sec_opciones,index=sec_opciones.index(sec_sel_b),
                     key="bib_sec_select",label_visibility="collapsed")
    if sel!=sec_sel_b:
        ss("bib_sec_filtro",sel); st.rerun()

    quizzes_fb=quizzes if sec_sel_b=="Todas" else [q for q in quizzes if (q.get("seccion") or "Sin seccion")==sec_sel_b]
    grupos={}
    for q in quizzes_fb:
        sec=q.get("seccion") or "Sin seccion"
        if sec not in grupos: grupos[sec]=[]
        grupos[sec].append(q)

    for sec,qs in grupos.items():
        es_sin_sec=sec=="Sin seccion"
        icono="📁" if es_sin_sec else "📂"
        st.markdown(f'<div class="section-header"><h3>{icono} {sec}</h3><span>{len(qs)} cuestionario{"s" if len(qs)!=1 else ""}</span></div>',unsafe_allow_html=True)

        if not es_sin_sec:
            sa1,sa2=st.columns(2)
            edit_sec_key=f"edit_sec_open_{sec}"
            confirm_sec_key=f"confirm_del_sec_{sec}"
            with sa1:
                lbl_edit_sec="✖ Cerrar" if gs(edit_sec_key) else "✏️ Renombrar seccion"
                if st.button(lbl_edit_sec, key=f"bib_sec_edit_{sec}", use_container_width=True):
                    ss(edit_sec_key, not gs(edit_sec_key,False))
                    if gs(confirm_sec_key): ss(confirm_sec_key,False)
                    st.rerun()
            with sa2:
                esperando_sec=gs(confirm_sec_key,False)
                lbl_del_sec="⚠️ ¿Seguro?" if esperando_sec else "🗑 Eliminar seccion"
                if st.button(lbl_del_sec, key=f"bib_sec_del_{sec}", use_container_width=True,
                             type="primary" if esperando_sec else "secondary"):
                    if esperando_sec:
                        ss(confirm_sec_key,False)
                        ss("_accion_bd",{"tipo":"eliminar_seccion","seccion":sec})
                        ss("bib_sec_filtro","Todas")
                    else:
                        ss(confirm_sec_key,True)
                        if gs(edit_sec_key): ss(edit_sec_key,False)
                    st.rerun()
            if gs(edit_sec_key):
                nuevo_nombre_sec=st.text_input("Nuevo nombre de seccion",value=sec,key=f"bib_sec_newname_{sec}")
                r1,r2=st.columns(2)
                with r1:
                    if st.button("💾 Guardar",type="primary",use_container_width=True,key=f"bib_sec_save_{sec}"):
                        n_limpio=nuevo_nombre_sec.strip()
                        if n_limpio and n_limpio!=sec:
                            ss(edit_sec_key,False)
                            ss("_accion_bd",{"tipo":"renombrar_seccion","seccion_vieja":sec,"seccion_nueva":n_limpio})
                            ss("bib_sec_filtro",n_limpio)
                        else: st.warning("Escribe un nombre distinto.")
                        st.rerun()
                with r2:
                    if st.button("Cancelar",use_container_width=True,key=f"bib_sec_cancel_{sec}"):
                        ss(edit_sec_key,False); st.rerun()

        for quiz in qs:
            st.markdown(f'<div class="quiz-item" style="border-left:4px solid #7c3aed;">'
                        f'<div class="quiz-title">{quiz["titulo"]}</div>'
                        f'<div style="margin-top:6px;">'
                        f'<span class="badge badge-gray">{quiz.get("n_preguntas",0)} preg</span>&nbsp;'
                        f'<span class="badge badge-gray">{quiz.get("n_alumnos",0)} alumnos</span>'
                        f'</div></div>',unsafe_allow_html=True)
            cb1,cb2,cb3=st.columns(3)
            with cb1:
                if st.button("✏️ Editar",key=f"bib_edit_{quiz['id_quiz']}",use_container_width=True):
                    ss("editar_quiz_id",quiz["id_quiz"]); ir("editar_quiz")
            with cb2:
                if st.button("📊 Notas",key=f"bib_notas_{quiz['id_quiz']}",use_container_width=True):
                    ss("resultados_quiz_id",quiz["id_quiz"])
                    ss("resultados_quiz_titulo",quiz["titulo"]); ir("resultados")
            with cb3:
                ckey=f"confirmar_del_{quiz['id_quiz']}"
                esperando=gs(ckey,False)
                lbl_del="⚠️ ¿Seguro?" if esperando else "🗑 Eliminar"
                if st.button(lbl_del,key=f"bib_del_{quiz['id_quiz']}",use_container_width=True,
                             type="primary" if esperando else "secondary"):
                    if esperando:
                        ss(ckey,False); ss("_accion_bd",{"tipo":"eliminar_quiz","id_quiz":quiz["id_quiz"]})
                    else:
                        ss(ckey,True)
                    st.rerun()
            st.markdown("<hr>",unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  EDITAR QUIZ
# ════════════════════════════════════════════════════════════════════
def pg_editar_quiz():
    render_topbar(gs("nombre_sala"))
    id_quiz=gs("editar_quiz_id"); profe_id=gs("profe_id")
    if not id_quiz or not profe_id: ir("biblioteca"); return
    if st.button("← Volver a Biblioteca",key="ed_back"): ir("biblioteca"); return
    try:
        db=conectar(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT * FROM quizzes WHERE id_quiz=%s AND id_profesor=%s",(id_quiz,profe_id))
        quiz=cur.fetchone()
        cur.execute("SELECT * FROM preguntas WHERE id_quiz=%s ORDER BY id_pregunta",(id_quiz,))
        preguntas=cur.fetchall()
        for p in preguntas:
            if p["tipo"]=="test":
                cur.execute("SELECT * FROM opciones WHERE id_pregunta=%s ORDER BY id_opcion",(p["id_pregunta"],))
                p["opciones"]=cur.fetchall()
            else: p["opciones"]=[]
        db.close()
    except Exception as e: st.error(f"Error: {e}"); return
    if not quiz: st.error("Quiz no encontrado."); return

    st.markdown(f'<div class="card-purple"><h2 style="color:white;margin:0 0 6px;">Editar Quiz</h2>'
                f'<p style="color:rgba(255,255,255,.85);margin:0;">{quiz["titulo"]} · {len(preguntas)} preguntas</p></div>',unsafe_allow_html=True)
    if gs("_ok_msg"): st.success(st.session_state.pop("_ok_msg"))
    if gs("_error_msg"): st.error(st.session_state.pop("_error_msg"))

    st.markdown("### Informacion del quiz")
    nuevo_titulo=st.text_input("Titulo",value=quiz["titulo"],key="ed_titulo")
    try:
        db=conectar(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT DISTINCT seccion FROM quizzes WHERE id_profesor=%s AND seccion IS NOT NULL AND seccion!='' ORDER BY seccion",(profe_id,))
        secs_ex=[r["seccion"] for r in cur.fetchall()]; db.close()
    except: secs_ex=[]
    sec_actual=quiz.get("seccion") or "Sin seccion"
    opts_sec=["Sin seccion"]+secs_ex+["Nueva seccion..."]
    idx_def=opts_sec.index(sec_actual) if sec_actual in opts_sec else 0
    sel_sec=st.selectbox("Seccion",opts_sec,index=idx_def,key="ed_sec_sel")
    if sel_sec=="Nueva seccion...":
        ns=st.text_input("Nueva seccion",key="ed_sec_nueva"); seccion_final=ns.strip() or None
    elif sel_sec=="Sin seccion": seccion_final=None
    else: seccion_final=sel_sec
    if st.button("Guardar titulo y seccion",type="primary",use_container_width=True,key="ed_save_meta"):
        if not nuevo_titulo.strip(): st.error("El titulo no puede estar vacio.")
        else:
            ss("_editar_quiz_bd",{"id_quiz":id_quiz,"titulo":nuevo_titulo.strip(),"seccion":seccion_final})
            st.rerun()

    st.markdown("<br>",unsafe_allow_html=True)
    COLORES_TIPO={"test":"#7c3aed","corta":"#059669"}
    LABEL_TIPO={"test":"Prueba","corta":"Corta"}
    st.markdown(f'<div style="font-weight:900;color:#4c1d95;font-size:1.05rem;margin-bottom:12px;">Preguntas ({len(preguntas)})</div>',unsafe_allow_html=True)

    for i,p in enumerate(preguntas):
        tipo=p.get("tipo","corta"); color=COLORES_TIPO.get(tipo,"#6b7280"); label=LABEL_TIPO.get(tipo,tipo)
        try: enunc=json.loads(p["enunciado"]).get("texto",p["enunciado"])
        except: enunc=p["enunciado"]

        st.markdown(f"""<div style="background:white;border-radius:14px;padding:14px 18px;
             margin-bottom:6px;border-left:5px solid {color};box-shadow:0 2px 8px rgba(0,0,0,.05);">
            <span style="background:{color};color:white;border-radius:20px;padding:2px 10px;font-size:.72rem;font-weight:800;">{label}</span>
            <div style="font-weight:700;color:#1f2937;margin-top:8px;font-size:.93rem;">{i+1}. {enunc}</div>
            <div style="color:#9ca3af;font-size:.8rem;margin-top:4px;">Respuesta: <em>{p.get("respuesta_modelo","")}</em></div>
        </div>""",unsafe_allow_html=True)

        editing_key=f"ed_editing_{p['id_pregunta']}"
        confirm_del_key=f"ed_confirmdel_{p['id_pregunta']}"
        col_e,col_d=st.columns(2)
        with col_e:
            lbl_edit="✖ Cerrar edicion" if gs(editing_key,False) else "✏️ Editar pregunta"
            if st.button(lbl_edit,key=f"ed_editbtn_{p['id_pregunta']}",use_container_width=True):
                ss(editing_key,not gs(editing_key,False)); st.rerun()
        with col_d:
            esperando_del=gs(confirm_del_key,False)
            lbl_del_p="⚠️ ¿Seguro?" if esperando_del else "🗑 Eliminar"
            if st.button(lbl_del_p,key=f"ed_delbtn_{p['id_pregunta']}",use_container_width=True,
                         type="primary" if esperando_del else "secondary"):
                if esperando_del:
                    ss(confirm_del_key,False)
                    ss("_accion_bd",{"tipo":"eliminar_pregunta","id_pregunta":p["id_pregunta"]})
                else:
                    ss(confirm_del_key,True)
                st.rerun()

        if gs(editing_key,False):
            st.markdown("---")
            nuevo_enunc=st.text_area("Enunciado",value=enunc,key=f"ed_enc_{p['id_pregunta']}",height=80)
            tipo_edit_sel=st.radio("Tipo",["Respuesta corta","Test (opciones)"],
                                   index=0 if tipo=="corta" else 1,
                                   key=f"ed_tipoedit_{p['id_pregunta']}",horizontal=True)
            tipo_edit="corta" if tipo_edit_sel=="Respuesta corta" else "test"
            nuevo_rm=st.text_input("Respuesta correcta / modelo",value=p.get("respuesta_modelo",""),key=f"ed_rm_{p['id_pregunta']}")
            nuevas_ops=[]
            if tipo_edit=="test":
                opciones_actuales=p.get("opciones",[]) if tipo=="test" else []
                n_ops_default=min(max(len(opciones_actuales),2),4)
                n_ops=st.selectbox("Numero de opciones",options=[2,3,4],
                                   index=[2,3,4].index(n_ops_default) if n_ops_default in [2,3,4] else 2,
                                   format_func=lambda x:f"{x} opciones",key=f"ed_nops_{p['id_pregunta']}")
                idx_correcto_previo=1
                for jj,oo in enumerate(opciones_actuales):
                    if oo.get("es_correcta"): idx_correcto_previo=jj+1; break
                idx_correcta=st.selectbox("Opcion correcta",range(1,n_ops+1),
                                          index=min(idx_correcto_previo-1,n_ops-1),
                                          format_func=lambda x:f"Opcion {x}",key=f"ed_idxc_{p['id_pregunta']}")
                for j in range(n_ops):
                    val_act=(opciones_actuales[j]["texto_opcion"] if j<len(opciones_actuales) else "")
                    lbl_op=f"✅ Opcion {j+1} (correcta)" if (j+1)==idx_correcta else f"Opcion {j+1}"
                    op_txt=st.text_input(lbl_op,value=val_act,key=f"ed_op_{p['id_pregunta']}_{j}")
                    nuevas_ops.append({"texto":op_txt,"correcta":(j+1)==idx_correcta})
            c_save,c_cancel=st.columns(2)
            with c_save:
                if st.button("Guardar cambios",type="primary",use_container_width=True,key=f"ed_save_{p['id_pregunta']}"):
                    if not nuevo_enunc.strip(): st.error("El enunciado no puede estar vacio.")
                    elif not nuevo_rm.strip(): st.error("La respuesta modelo no puede estar vacia.")
                    elif tipo_edit=="test" and any(not o["texto"].strip() for o in nuevas_ops): st.error("Rellena todas las opciones.")
                    else:
                        ss("_accion_bd",{"tipo":"editar_pregunta","id_pregunta":p["id_pregunta"],
                                         "tipo_preg":tipo_edit,"enunciado":nuevo_enunc.strip(),
                                         "respuesta_modelo":nuevo_rm.strip(),
                                         "opciones":nuevas_ops if tipo_edit=="test" else []})
                        ss(editing_key,False); st.rerun()
            with c_cancel:
                if st.button("Cancelar",use_container_width=True,key=f"ed_cancel_{p['id_pregunta']}"):
                    ss(editing_key,False); st.rerun()
            st.markdown("---")

        st.markdown("<hr>",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    st.markdown('<div style="font-weight:900;color:#4c1d95;font-size:1.05rem;margin-bottom:14px;">Añadir nueva pregunta</div>',unsafe_allow_html=True)
    tipo_nueva=st.radio("Tipo de pregunta",["Respuesta corta","Test (opciones)"],key="ed_add_tipo",horizontal=True)
    enunc_nueva=st.text_area("Enunciado de la pregunta",key="ed_add_enc",height=80,placeholder="Escribe aqui la nueva pregunta...")
    rm_nueva=st.text_input("Respuesta correcta / modelo",key="ed_add_rm",placeholder="Texto exacto de la opcion correcta o respuesta esperada...")
    ops_nuevas_add=[]
    if tipo_nueva=="Test (opciones)":
        n_ops_add=st.selectbox("Numero de opciones",options=[2,3,4],index=2,format_func=lambda x:f"{x} opciones",key="ed_add_nops")
        for j in range(1,n_ops_add):
            op_extra=st.text_input(f"Opcion incorrecta {j}",key=f"ed_add_op_{j}",placeholder=f"Opcion {j+1}...")
            ops_nuevas_add.append({"texto":op_extra.strip(),"correcta":False})
    if st.button("Guardar nueva pregunta",type="primary",use_container_width=True,key="ed_add_save"):
        if not enunc_nueva.strip(): st.error("Escribe el enunciado.")
        elif not rm_nueva.strip(): st.error("Escribe la respuesta modelo.")
        elif tipo_nueva=="Test (opciones)" and any(not o["texto"] for o in ops_nuevas_add): st.error("Rellena todas las opciones incorrectas.")
        else:
            tipo_bd="test" if tipo_nueva=="Test (opciones)" else "corta"
            ops_completas=([{"texto":rm_nueva.strip(),"correcta":True}]+ops_nuevas_add) if tipo_bd=="test" else []
            ss("_accion_bd",{"tipo":"añadir_pregunta","id_quiz":id_quiz,"enunciado":enunc_nueva.strip(),
                             "tipo_preg":tipo_bd,"respuesta_modelo":rm_nueva.strip(),"opciones":ops_completas})
            st.rerun()

    st.markdown("<br>",unsafe_allow_html=True)
    ckey_quiz=f"confirmar_del_quiz_{id_quiz}"
    esperando_quiz=gs(ckey_quiz,False)
    lbl_quiz_del="⚠️ Confirmar: eliminar quiz completo" if esperando_quiz else "🗑 Eliminar este quiz completo"
    if st.button(lbl_quiz_del,use_container_width=True,key="ed_del",type="primary" if esperando_quiz else "secondary"):
        if esperando_quiz:
            ss(ckey_quiz,False); ss("_accion_bd",{"tipo":"eliminar_quiz","id_quiz":id_quiz}); ir("biblioteca")
        else:
            ss(ckey_quiz,True); st.rerun()


# ════════════════════════════════════════════════════════════════════
#  RESULTADOS
# ════════════════════════════════════════════════════════════════════
def pg_resultados():
    render_topbar(gs("nombre_sala"))
    id_quiz=gs("resultados_quiz_id"); titulo=gs("resultados_quiz_titulo","Examen")
    if st.button("← Volver a Biblioteca",key="res_back"): ir("biblioteca"); return
    st.markdown(f'<div class="card-blue"><h2 style="color:white;margin:0 0 4px;">📊 {titulo}</h2>'
                f'<p style="color:rgba(255,255,255,.85);margin:0;">Notas y correcciones por alumno</p></div>',unsafe_allow_html=True)
    if gs("_nota_ok"): st.success(st.session_state.pop("_nota_ok"))
    if gs("_nota_err"): st.error(st.session_state.pop("_nota_err"))
    if not id_quiz: st.error("No hay quiz seleccionado."); return
    try:
        db=conectar(); cur=db.cursor(dictionary=True)
        cur.execute("SELECT id_pregunta,enunciado,tipo,respuesta_modelo FROM preguntas WHERE id_quiz=%s ORDER BY id_pregunta",(id_quiz,))
        preguntas_ord=cur.fetchall()
        cur.execute("""SELECT ra.id_respuesta,ra.nombre_alumno,ra.id_pregunta,
                   ra.contenido_respuesta,p.respuesta_modelo,ra.puntuacion,p.tipo,p.enunciado
                   FROM respuestas_alumnos ra LEFT JOIN preguntas p ON ra.id_pregunta=p.id_pregunta
                   WHERE ra.id_quiz=%s ORDER BY ra.nombre_alumno,p.id_pregunta""",(id_quiz,))
        filas=cur.fetchall(); db.close()
    except Exception as e: st.error(f"Error: {e}"); return
    if not filas: st.info("Ningun alumno ha enviado el examen todavia."); return

    alumnos={}
    for f in filas:
        n=f["nombre_alumno"]
        if n not in alumnos: alumnos[n]={}
        alumnos[n][f["id_pregunta"]]=f
    nombres=list(alumnos.keys())
    n_preguntas=len(preguntas_ord)

    filas_tabla=""
    alumno_sel_cur=gs("res_alumno_sel","")
    for n_a in nombres:
        rs=alumnos[n_a]
        total=sum(float(r.get("puntuacion") or 0) for r in rs.values())
        nt=sum(1 for r in rs.values() if r.get("tipo")=="test")
        nb=sum(1 for r in rs.values() if r.get("tipo")=="test" and
               str(r.get("contenido_respuesta") or "").strip().lower()==str(r.get("respuesta_modelo") or "").strip().lower())
        hl="background:#ede9fe;" if n_a==alumno_sel_cur else ""
        filas_tabla+=(f'<tr style="{hl}"><td style="padding:10px 16px;font-weight:700;">{n_a}</td>'
                      f'<td style="padding:10px 16px;text-align:center;font-weight:800;color:#7c3aed;">{total:.1f}</td>'
                      f'<td style="padding:10px 16px;text-align:center;color:#6b7280;">{nb}/{nt} test</td></tr>')
    st.markdown(f"""<div class="card" style="padding:0;overflow:hidden;"><table style="width:100%;border-collapse:collapse;">
        <thead><tr style="background:#f9fafb;border-bottom:2px solid #e5e7eb;">
            <th style="padding:12px 16px;text-align:left;color:#6b7280;font-size:.8rem;text-transform:uppercase;">Alumno</th>
            <th style="padding:12px 16px;text-align:center;color:#6b7280;font-size:.8rem;text-transform:uppercase;">Nota total</th>
            <th style="padding:12px 16px;text-align:center;color:#6b7280;font-size:.8rem;text-transform:uppercase;">Test</th>
        </tr></thead><tbody>{filas_tabla}</tbody></table></div>""",unsafe_allow_html=True)

    buf=io.StringIO(); ww=csv.writer(buf)
    ww.writerow(["ALUMNO","Nota"]+[f"P{i+1}" for i in range(n_preguntas)])
    for n_a in nombres:
        rs=alumnos[n_a]
        nota_total=sum(float(r.get("puntuacion") or 0) for r in rs.values())
        fila=[n_a, f"{nota_total:.1f}"]
        for pq in preguntas_ord:
            r=rs.get(pq["id_pregunta"])
            if r:
                punt=float(r.get("puntuacion") or 0)
                fila.append(int(punt) if punt==int(punt) else str(punt).replace(",","."))
            else:
                fila.append("")
        ww.writerow(fila)
    st.download_button(f"📥 Descargar CSV ({len(nombres)} alumnos)",
                       data=buf.getvalue().encode("utf-8"),
                       file_name=f"notas_{titulo.replace(' ','_')}.csv",
                       mime="text/csv", key="csv_completo")

    st.markdown("<br>",unsafe_allow_html=True)
    alumno_sel=st.selectbox("Ver detalle de alumno",options=nombres,key="res_alumno_sel")
    if alumno_sel:
        rs=alumnos[alumno_sel]
        total=sum(float(r.get("puntuacion") or 0) for r in rs.values())
        st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;background:white;border-radius:16px;padding:16px 22px;margin:16px 0;box-shadow:0 4px 16px rgba(107,70,193,0.08);border:1px solid #e5e7eb;">'
                    f'<span style="font-size:1.1rem;font-weight:900;color:#4c1d95;">{alumno_sel}</span>'
                    f'<span style="background:#ede9fe;color:#5b21b6;border-radius:20px;padding:4px 14px;font-size:.85rem;font-weight:800;">{total:.1f} pts</span></div>',unsafe_allow_html=True)
        for idx,pq in enumerate(preguntas_ord):
            r=rs.get(pq["id_pregunta"])
            try: etxt=json.loads(pq["enunciado"]).get("texto",pq["enunciado"])
            except: etxt=pq.get("enunciado","")
            if r:
                if r.get("tipo")=="test":
                    ok=str(r.get("contenido_respuesta") or "").strip().lower()==str(r.get("respuesta_modelo") or "").strip().lower()
                    badge=('<span class="badge badge-ok">Correcto</span>' if ok else '<span class="badge badge-fail">Incorrecto</span>')
                    borde="#10b981" if ok else "#ef4444"
                else: badge='<span class="badge badge-warn">Correccion manual</span>'; borde="#f59e0b"
                resp_txt=r.get("contenido_respuesta",""); punt_txt=str(float(r.get("puntuacion") or 0))
                rid=r["id_respuesta"]; pun=r.get("puntuacion",0)
            else:
                badge='<span class="badge badge-gray">Sin respuesta</span>'; borde="#d1d5db"
                resp_txt=""; punt_txt="0.0"; rid=f"vacio_{idx}"; pun=0
            st.markdown(f'<div class="res-row" style="border-left:4px solid {borde};">'
                        f'<strong>P{idx+1}. {etxt}</strong><br>'
                        f'<span style="color:#6b7280;font-size:.82rem;">Modelo: <em>{pq.get("respuesta_modelo","")}</em></span><br>'
                        f'<span style="color:#374151;">Alumno: <strong>{resp_txt}</strong></span>'
                        f'&nbsp;&nbsp;{badge}</div>',unsafe_allow_html=True)
            st.text_input(f"Nota P{idx+1}",value=punt_txt,key=f"nota_{rid}",
                          label_visibility="collapsed",placeholder="0.0 - 10.0",disabled=not bool(r))
            def _guardar(rid=rid, pun=pun):
                txt=st.session_state.get(f"nota_{rid}",str(float(pun or 0)))
                try: v=max(0.0,min(10.0,float(txt.replace(",","."))))
                except: v=float(pun or 0)
                ss("_guardar_nota",{"id":rid,"nota":v,"alumno":st.session_state.get("res_alumno_sel","")})
            st.button(f"Guardar nota P{idx+1}",key=f"ok_{rid}",on_click=_guardar,disabled=not bool(r))
            st.markdown("<hr>",unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
#  CREAR QUIZ IA
# ════════════════════════════════════════════════════════════════════
def pg_crear_ia():
    render_topbar(gs("nombre_sala"))
    if st.button("← Volver al Launcher",key="ia_back"): ir("launcher"); return
    st.markdown('<div class="card-purple"><h2 style="color:white;margin:0 0 6px;">Generar Quiz con IA</h2>'
                '<p style="color:rgba(255,255,255,.85);margin:0;">Escribe el tema y la IA generara las preguntas.</p></div>',unsafe_allow_html=True)
    tema=st.text_input("Tema del examen",placeholder="Ej: La Revolucion Francesa, Fotosintesis...",key="ia_tema")
    cantidad=st.number_input("Numero de preguntas",min_value=1,max_value=30,value=5,step=1,key="ia_cant")
    seccion=widget_seccion(gs("profe_id"),key_prefix="ia")
    if st.button("Generar Quiz ahora",type="primary",use_container_width=True,key="ia_gen"):
        if not tema.strip(): st.error("Escribe un tema primero.")
        else:
            with st.spinner(f"Generando {int(cantidad)} preguntas sobre {tema}..."):
                try:
                    data=generar_quiz_ia(tema.strip(),int(cantidad),es_documento=False)
                    guardar_quiz_bd(data,gs("profe_id"),seccion=seccion)
                    ss("_ok_msg",f"Quiz creado con {len(data.get('preguntas',[]))} preguntas.")
                    ir("launcher")
                except Exception as e: st.error(f"Error: {e}")

# ════════════════════════════════════════════════════════════════════
#  CREAR QUIZ DESDE DOCUMENTO
#  FIX removeChild: la llamada a la IA va al bloque temprano
#  (_doc_generar_pendiente), no dentro de la función de render.
#  Así cuando st.rerun() ocurre, el DOM parte de cero sin widgets
#  previos que React tenga que reconciliar.
# ════════════════════════════════════════════════════════════════════
def pg_crear_doc():
    if gs("doc_borrador") is not None:
        _pg_crear_doc_revisar()
    else:
        _pg_crear_doc_subir()

def _pg_crear_doc_subir():
    render_topbar(gs("nombre_sala"))
    if st.button("← Volver al Launcher", key="doc_back"):
        ir("launcher"); return
    st.markdown('<div class="card-teal"><h2 style="color:white;margin:0 0 6px;">Quiz desde Documento</h2>'
                '<p style="color:rgba(255,255,255,.9);margin:0;">Sube un TXT o CSV · La IA genera preguntas · Revisa y guarda.</p></div>', unsafe_allow_html=True)

    if gs("_doc_error"): st.error(st.session_state.pop("_doc_error"))

    archivo     = st.file_uploader("Selecciona tu archivo (TXT o CSV)", type=["txt","csv"], key="doc_file")
    cantidad    = st.number_input("Numero de preguntas a generar", min_value=1, max_value=30, value=8, step=1, key="doc_cant")
    titulo_extra= st.text_input("Titulo del quiz (opcional)", key="doc_tit", placeholder="La IA lo genera si lo dejas vacio")
    seccion     = widget_seccion(gs("profe_id"), key_prefix="doc")

    if archivo:
        try:
            raw = archivo.read()
            try: contenido = raw.decode("utf-8")
            except: contenido = raw.decode("latin-1", errors="replace")
            if archivo.name.lower().endswith(".csv"):
                lineas = []
                for fila in csv.reader(io.StringIO(contenido)):
                    linea = " | ".join(c.strip() for c in fila if c.strip())
                    if linea: lineas.append(linea)
                contenido = "\n".join(lineas)
            st.markdown(f'<div class="card-green"><strong>{archivo.name}</strong> cargado — {len(contenido):,} caracteres</div>', unsafe_allow_html=True)
            if st.checkbox("Ver vista previa", key="doc_preview"):
                st.text_area("", contenido[:3000] + ("..." if len(contenido) > 3000 else ""),
                             height=180, disabled=True, label_visibility="collapsed")

            # KEY FIX: al pulsar Generar, NO llamamos a la IA aquí.
            # Guardamos los datos en _doc_generar_pendiente y hacemos rerun.
            # El bloque temprano (antes de set_page_config) llama a la IA
            # y vuelve a hacer rerun — así el cambio de árbol ocurre entre
            # dos renders limpios, sin widgets intermedios que confundan a React.
            if st.button(f"Generar {int(cantidad)} preguntas del documento", type="primary",
                         use_container_width=True, key="doc_gen"):
                ss("_doc_generar_pendiente", {
                    "contenido": contenido,
                    "cantidad": int(cantidad),
                    "titulo_extra": titulo_extra.strip(),
                    "seccion": seccion,
                })
                st.rerun()
        except Exception as e: st.error(f"Error leyendo archivo: {e}")
    else:
        st.markdown('<div style="text-align:center;padding:40px;background:#f9fafb;border-radius:16px;'
                    'border:2px dashed #d1d5db;"><div style="font-size:2.5rem;">📂</div>'
                    '<div style="font-weight:700;color:#6b7280;">Sube un archivo TXT o CSV</div></div>',
                    unsafe_allow_html=True)

def _pg_crear_doc_revisar():
    render_topbar(gs("nombre_sala"))
    borrador       = gs("doc_borrador", [])
    titulo_actual  = gs("doc_titulo_base", "Quiz")
    contenido_orig = gs("doc_contenido", "")

    st.markdown('''<div class="card-teal"><h2 style="color:white;margin:0 0 6px;">Quiz desde Documento</h2>
                <p style="color:rgba(255,255,255,.9);margin:0;">Revisa las preguntas y guarda cuando estés listo.</p></div>''',
                unsafe_allow_html=True)
    st.markdown(f'<div style="background:white;border-radius:16px;padding:14px 22px;margin-bottom:18px;'
                f'border-left:6px solid #06b6d4;font-size:1.05rem;font-weight:900;color:#0e7490;">'
                f'📋 {len(borrador)} preguntas generadas</div>', unsafe_allow_html=True)

    if gs("_doc_error"): st.error(st.session_state.pop("_doc_error"))
    if gs("_ok_msg"):    st.success(st.session_state.pop("_ok_msg"))

    nuevo_titulo = st.text_input("Titulo del quiz", value=titulo_actual, key="doc_titulo_edit2")

    col_g, col_c, col_b = st.columns(3)
    with col_g:
        st.button("💾 Guardar quiz", type="primary", use_container_width=True,
                  key="doc_btn_guardar",
                  on_click=lambda: ss("_doc_accion", {
                      "tipo": "guardar",
                      "titulo": gs("doc_titulo_edit2") or titulo_actual
                  }))
    with col_c:
        n_extra = st.selectbox("Cuantas mas", [1,2,3,4,5,6,8,10], index=2,
                               format_func=lambda x: f"{x} mas", key="doc_n_extra2",
                               label_visibility="collapsed")
    with col_b:
        st.button("✨ Generar mas", use_container_width=True,
                  key="doc_btn_generar",
                  on_click=lambda: ss("_doc_accion", {
                      "tipo": "generar_mas",
                      "titulo": gs("doc_titulo_edit2") or titulo_actual,
                      "n": gs("doc_n_extra2") or 3,
                      "contenido": contenido_orig
                  }))

    st.markdown("<br>", unsafe_allow_html=True)

    COLORES_TIPO = {"test": "#7c3aed", "corta": "#059669"}
    LABEL_TIPO   = {"test": "Test", "corta": "Corta"}
    for i, p in enumerate(borrador):
        tipo  = p.get("tipo", "corta")
        color = COLORES_TIPO.get(tipo, "#6b7280")
        label = LABEL_TIPO.get(tipo, tipo)
        st.markdown(
            f'<div style="background:white;border-radius:14px;padding:14px 18px;'
            f'border-left:5px solid {color};margin-bottom:4px;">'
            f'<span style="background:{color};color:white;border-radius:20px;'
            f'padding:2px 10px;font-size:.72rem;font-weight:800;">{label}</span>'
            f'<div style="font-weight:700;color:#1f2937;margin-top:6px;">{i+1}. {p.get("enunciado","")}</div>'
            f'<div style="color:#6b7280;font-size:.8rem;margin-top:3px;">'
            f'✅ {p.get("respuesta_modelo","")}</div></div>',
            unsafe_allow_html=True)
        st.button(f"🗑 Eliminar pregunta {i+1}", key=f"doc_del_{i}",
                  use_container_width=True,
                  on_click=lambda idx=i: ss("_doc_accion", {"tipo": "eliminar", "idx": idx}))
        st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.button("✖ Cancelar y volver", use_container_width=True, key="doc_btn_cancelar",
              on_click=lambda: ss("_doc_accion", {"tipo": "cancelar"}))


# ════════════════════════════════════════════════════════════════════
#  CREAR QUIZ MANUAL
# ════════════════════════════════════════════════════════════════════
def pg_crear_manual():
    render_topbar(gs("nombre_sala"))
    if st.button("← Volver al Launcher",key="man_back"): ir("launcher"); return
    st.markdown('<div class="card-orange"><h2 style="color:white;margin:0 0 6px;">Crear Quiz Manual</h2>'
                '<p style="color:rgba(255,255,255,.9);margin:0;">Diseña el examen pregunta a pregunta.</p></div>',unsafe_allow_html=True)
    if "num_preg_manual" not in st.session_state: ss("num_preg_manual",1)
    titulo=st.text_input("Titulo del Quiz",placeholder="Ej: Examen Biologia",key="man_tit")
    seccion=widget_seccion(gs("profe_id"),key_prefix="man")
    if st.button("Añadir pregunta",key="man_add"): ss("num_preg_manual",gs("num_preg_manual")+1); st.rerun()
    COLORES=["#7c3aed","#059669","#dc2626","#d97706","#0284c7","#db2777"]
    preguntas_data=[]
    for i in range(gs("num_preg_manual",1)):
        c=COLORES[i%len(COLORES)]
        st.markdown(f'<div style="background:white;border-radius:18px;padding:14px 20px;margin:14px 0 6px 0;border-left:6px solid {c};box-shadow:0 4px 16px rgba(0,0,0,.06);">'
                    f'<span style="background:{c};color:white;border-radius:20px;padding:4px 14px;font-size:.8rem;font-weight:800;">PREGUNTA {i+1}</span></div>',unsafe_allow_html=True)
        enunciado=st.text_input(f"Enunciado {i+1}",key=f"man_enc_{i}",placeholder=f"Escribe la pregunta {i+1}...",label_visibility="collapsed")
        mostrar_img=st.checkbox(f"Añadir imagen a pregunta {i+1} (opcional)",key=f"man_chk_{i}")
        imagen_final=""
        if mostrar_img:
            tipo_img=st.radio("","📁 Subir archivo,🔗 URL".split(","),key=f"man_imt_{i}",horizontal=True,label_visibility="collapsed")
            if tipo_img=="📁 Subir archivo":
                up=st.file_uploader("",type=["png","jpg","jpeg","gif","webp"],key=f"man_imf_{i}",label_visibility="collapsed")
                if up:
                    b64s=base64.b64encode(up.read()).decode(); imagen_final=f"data:{up.type};base64,{b64s}"; st.image(imagen_final,width=280)
            else:
                url_img=st.text_input("URL",key=f"man_imu_{i}",placeholder="https://...",label_visibility="collapsed")
                if url_img.strip():
                    imagen_final=url_img.strip()
                    try: st.image(url_img,width=280)
                    except: st.warning("No se puede previsualizar.")
        tipo_sel=st.radio(f"Tipo {i+1}",["Respuesta corta","Test — 2 opciones","Test — 4 opciones"],
                          key=f"man_tipo_{i}",horizontal=True,label_visibility="collapsed")
        tipo={"Respuesta corta":"corta","Test — 2 opciones":"test2","Test — 4 opciones":"test4"}[tipo_sel]
        opciones_data=[]; resp_modelo=""
        if tipo=="corta":
            resp_modelo=st.text_input(f"Respuesta modelo {i+1}",key=f"man_rm_{i}",placeholder="Respuesta esperada...")
        else:
            n_ops=2 if tipo=="test2" else 4
            idx_c=st.selectbox(f"Cual es la correcta? (P{i+1})",range(1,n_ops+1),format_func=lambda x:f"Opcion {x}",key=f"man_cor_{i}")
            for j in range(1,n_ops+1):
                lbl=f"Opcion {j} (correcta)" if j==idx_c else f"Opcion {j}"
                op_t=st.text_input(lbl,key=f"man_op_{i}_{j}",placeholder=f"Escribe la opcion {j}...")
                opciones_data.append({"texto":op_t,"correcta":j==idx_c})
                if j==idx_c: resp_modelo=op_t
        preguntas_data.append({"enunciado":enunciado,"tipo":tipo,"respuesta_modelo":resp_modelo,"imagen":imagen_final,"opciones":opciones_data})
    st.markdown("<br>",unsafe_allow_html=True)
    col_sv,col_cl=st.columns([3,1])
    with col_sv:
        if st.button("Guardar Quiz",use_container_width=True,type="primary",key="man_save"):
            if not titulo.strip(): st.error("El titulo es obligatorio.")
            elif not any(p["enunciado"].strip() for p in preguntas_data): st.error("Añade al menos una pregunta.")
            else:
                try:
                    db=conectar(); cur=db.cursor()
                    cur.execute("INSERT INTO quizzes (titulo,id_profesor,seccion) VALUES (%s,%s,%s)",(titulo.strip(),gs("profe_id"),seccion or None))
                    id_quiz=cur.lastrowid; guardadas=0
                    for p in preguntas_data:
                        if not p["enunciado"].strip(): continue
                        enc=(json.dumps({"texto":p["enunciado"],"imagen":p["imagen"]}) if p["imagen"] else p["enunciado"])
                        tipo_bd="test" if p["tipo"] in ("test2","test4") else "corta"
                        cur.execute("INSERT INTO preguntas (id_quiz,enunciado,tipo,respuesta_modelo) VALUES (%s,%s,%s,%s)",(id_quiz,enc,tipo_bd,p["respuesta_modelo"]))
                        id_preg=cur.lastrowid
                        for op in p["opciones"]:
                            if op["texto"].strip():
                                cur.execute("INSERT INTO opciones (id_pregunta,texto_opcion,es_correcta) VALUES (%s,%s,%s)",(id_preg,op["texto"],op["correcta"]))
                        guardadas+=1
                    db.commit(); db.close()
                    ss("_ok_msg",f"Quiz guardado con {guardadas} preguntas."); ss("num_preg_manual",1); ir("launcher")
                except Exception as e: st.error(f"Error: {e}")
    with col_cl:
        if st.button("Limpiar",use_container_width=True,key="man_clear"):
            ss("num_preg_manual",1); st.rerun()

# ════════════════════════════════════════════════════════════════════
main()