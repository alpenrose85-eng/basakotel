import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT.parent / "baza_dannykh" / "boilers_reference.json"

st.set_page_config(page_title="База котлов ТЭЦ", layout="wide")


def load_data() -> Dict:
    if not DATA_PATH.exists():
        return {"boilers": []}
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_data(data: Dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def flatten_surfaces(data: Dict) -> List[Dict]:
    rows: List[Dict] = []
    for boiler in data.get("boilers", []):
        for surface in boiler.get("surfaces", []):
            row = {
                "boiler_id": boiler.get("id"),
                "boiler_name": boiler.get("name"),
                "location": boiler.get("location"),
                "surface": surface.get("name"),
                "aliases": ", ".join(surface.get("aliases", [])) if surface.get("aliases") else "",
                "steel": surface.get("steel"),
                "pressure": surface.get("pressure"),
                "temperature": surface.get("temperature"),
                "outer_diameter": surface.get("outerDiameter"),
                "wall_thickness": surface.get("wallThickness"),
                "notes": surface.get("notes", ""),
                "load_condition": surface.get("loadCondition", ""),
            }
            rows.append(row)
    return rows


def match_query(item: Dict, query: str) -> bool:
    query = query.lower()
    for value in item.values():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            if query in " ".join(map(str, value)).lower():
                return True
        elif query in str(value).lower():
            return True
    return False


def find_boiler(data: Dict, boiler_id: str) -> Optional[Dict]:
    for boiler in data.get("boilers", []):
        if boiler.get("id") == boiler_id:
            return boiler
    return None


def merge_uploaded_boilers(existing: Dict, incoming: Dict) -> int:
    count = 0
    incoming_list = incoming.get("boilers", [])
    if not incoming_list:
        return count
    index = {boiler.get("id"): boiler for boiler in existing.get("boilers", [])}
    for candidate in incoming_list:
        candidate_id = candidate.get("id")
        candidate_surfaces = candidate.get("surfaces", [])
        if not candidate_id:
            continue
        target = index.get(candidate_id)
        if target is None:
            existing.setdefault("boilers", []).append(candidate)
            index[candidate_id] = candidate
            count += 1
            continue
        existing_surfaces = target.setdefault("surfaces", [])
        existing_names = {surface.get("name") for surface in existing_surfaces if surface.get("name")}
        for surface in candidate_surfaces:
            if surface.get("name") not in existing_names:
                existing_surfaces.append(surface)
                existing_names.add(surface.get("name"))
                count += 1
    return count


def build_surface_payload() -> Dict:
    with st.form("add_surface"):
        st.subheader("Добавить поверхность")
        form_columns = st.columns(2)
        with form_columns[0]:
            surface_name = st.text_input("Название поверхности", value="", help="Например, Пароперегреватель")
            aliases_raw = st.text_input("Альтернативные названия через запятую")
            steel = st.text_input("Марка стали")
            pressure = st.number_input("Давление, МПа", min_value=0.0, format="%.4f")
            temperature = st.number_input("Температура, °C", min_value=0.0, format="%.1f")
        with form_columns[1]:
            outer_diameter = st.number_input("Наружный диаметр, мм", min_value=0.0, format="%.1f")
            wall_thickness = st.number_input("Толщина стенки, мм", min_value=0.0, format="%.1f")
            load_condition = st.text_input("Условие загрузки (например, 100%)")
            notes = st.text_area("Примечания", height=120)
        submit = st.form_submit_button("Сохранить поверхность")
    if not submit:
        return {}
    return {
        "name": surface_name.strip() or "",
        "aliases": [alias.strip() for alias in aliases_raw.split(",") if alias.strip()],
        "steel": steel.strip() or None,
        "pressure": pressure if pressure > 0 else None,
        "temperature": temperature if temperature > 0 else None,
        "outerDiameter": outer_diameter if outer_diameter > 0 else None,
        "wallThickness": wall_thickness if wall_thickness > 0 else None,
        "loadCondition": load_condition.strip() or None,
        "notes": notes.strip() or None,
    }


def main() -> None:
    st.title("База поверхностей нагрева")
    st.write(
        "Эта панель использует базу в `work/baza_dannykh/boilers_reference.json`. Поиск по слову возвращает все совпадения по котлу, поверхности и материалу."
    )

    data = load_data()
    total_boilers = len(data.get("boilers", []))
    total_surfaces = len(flatten_surfaces(data))

    st.metric("Всего котлов", total_boilers)
    st.metric("Всего поверхностей", total_surfaces)

    st.header("Поиск")
    query = st.text_input("Найти по котлу/поверхности/марке стали", value="")
    flattened = flatten_surfaces(data)
    if query:
        matches = [row for row in flattened if match_query(row, query)]
        st.success(f"Найдено {len(matches)} совпадений")
    else:
        matches = flattened
    if matches:
        st.dataframe(pd.DataFrame(matches).fillna(""))
    else:
        st.info("Совпадений ещё нет — добавьте первую поверхность")

    st.header("Добавление данных")
    boiler_options = [boiler.get("id") for boiler in data.get("boilers", []) if boiler.get("id")] or ["Новый котёл"]
    boiler_selection = st.selectbox("Выберите существующий котёл или создайте новый", ["Новый котёл"] + boiler_options)
    new_boiler: Dict = {}
    if boiler_selection == "Новый котёл":
        new_boiler_id = st.text_input("ID нового котла", key="new_boiler_id")
        new_boiler_name = st.text_input("Название нового котла", key="new_boiler_name")
        new_location = st.text_input("Расположение", key="new_boiler_location")
        new_notes = st.text_area("Примечания к котлу", key="new_boiler_notes")
        new_boiler = {
            "id": new_boiler_id.strip(),
            "name": new_boiler_name.strip() or None,
            "location": new_location.strip() or None,
            "notes": new_notes.strip() or None,
        }
    surface_payload = build_surface_payload()
    if surface_payload:
        if not surface_payload.get("name"):
            st.error("Введите название поверхности")
        else:
            if boiler_selection == "Новый котёл":
                if not new_boiler.get("id"):
                    st.error("Задайте ID нового котла")
                else:
                    new_record = {key: value for key, value in new_boiler.items() if value}
                    new_record["surfaces"] = [surface_payload]
                    data.setdefault("boilers", []).append(new_record)
                    save_data(data)
                    st.success("Добавлен новый котёл и поверхность")
            else:
                target = find_boiler(data, boiler_selection)
                if target is None:
                    st.error("Выбранный котёл не найден")
                else:
                    target.setdefault("surfaces", []).append(surface_payload)
                    save_data(data)
                    st.success("Поверхность добавлена к существующему котлу")

    st.header("Загрузка данных из файла")
    uploaded = st.file_uploader("Загрузите JSON с массивом boilers", type=["json"])
    if uploaded:
        try:
            incoming = json.load(uploaded)
        except json.JSONDecodeError as exc:
            st.error(f"Не удалось прочитать файл: {exc}")
            return
        added = merge_uploaded_boilers(data, incoming)
        if added:
            save_data(data)
            st.success(f"Импортировано {added} новых записей/поверхностей")
        else:
            st.info("Файл обработан, но новых поверхностей не добавлено")

    st.header("Исходные данные")
    with st.expander("Посмотреть JSON-структуру базы"):  # noqa: SIM101
        st.json(data)


if __name__ == "__main__":
    main()
