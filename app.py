import json
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT.parent / "baza_dannykh" / "boilers_reference.json"

st.set_page_config(page_title="База котлов ТЭЦ", layout="wide")


SURFACE_COLUMNS = [
    "boiler_id",
    "boiler_name",
    "station",
    "boiler_type",
    "category",
    "system",
    "surface",
    "surface_group",
    "section",
    "aliases",
    "steel",
    "pressure",
    "temperature",
    "outer_diameter",
    "wall_thickness",
    "notes",
]


def load_data() -> Dict:
    if not DATA_PATH.exists():
        return {"boilers": []}
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_data(data: Dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def get_boiler_parameters(boiler: Dict) -> Dict:
    params = boiler.get("parameters", {}) or {}
    result = {
        "steam_flow": params.get("steam_flow_tph")
        or (params.get("steam", {}) or {}).get("power_tph"),
        "superheated_pressure": params.get("superheated_pressure_mpa")
        or params.get("superheated_pressure_kgf_cm2"),
        "superheated_temp": params.get("superheated_temp"),
        "secondary_pressure": (params.get("secondary_steam", {}) or {}).get("pressure_in_kgf_cm2"),
        "secondary_temp": (params.get("secondary_steam", {}) or {}).get("temperature_out"),
        "fuel": params.get("fuel"),
        "notes": boiler.get("notes"),
    }
    return result


def flatten_surfaces(data: Dict) -> List[Dict]:
    rows: List[Dict] = []
    for boiler in data.get("boilers", []):
        boiler_info = {
            "boiler_id": boiler.get("id"),
            "boiler_name": boiler.get("name"),
            "station": boiler.get("station"),
            "boiler_type": boiler.get("boilerType"),
        }
        for surface in boiler.get("surfaces", []):
            base_row = {
                **boiler_info,
                "surface": surface.get("name"),
                "surface_group": surface.get("surface_group"),
                "section": surface.get("section"),
                "aliases": ", ".join(surface.get("aliases", [])) if surface.get("aliases") else "",
                "category": surface.get("category"),
                "system": surface.get("system"),
                "steel": surface.get("steel"),
                "pressure": surface.get("pressure"),
                "temperature": surface.get("temperature"),
                "outer_diameter": surface.get("outerDiameter"),
                "wall_thickness": surface.get("wallThickness"),
                "notes": surface.get("notes", ""),
            }
            components = surface.get("components", [])
            if not components:
                rows.append(base_row)
            else:
                for component in components:
                    rows.append({
                        **boiler_info,
                        "surface": f"{surface.get('name')} — {component.get('description')}",
                        "surface_group": surface.get("surface_group"),
                        "section": component.get("section") or surface.get("section"),
                        "aliases": ", ".join(surface.get("aliases", [])) if surface.get("aliases") else "",
                        "category": surface.get("category"),
                        "system": surface.get("system"),
                        "steel": component.get("steel"),
                        "pressure": component.get("pressure"),
                        "temperature": component.get("temperature"),
                        "outer_diameter": component.get("outerDiameter"),
                        "wall_thickness": component.get("wallThickness"),
                        "notes": component.get("notes", surface.get("notes", "")),
                    })
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


def collect_unique(data: List[Dict], key: str) -> List[str]:
    values = {item[key] for item in data if item.get(key)}
    return sorted(values)


def build_boiler_table(data: Dict) -> List[Dict]:
    rows = []
    for boiler in data.get("boilers", []):
        params = boiler.get("parameters", {}) or {}
        row = {
            "boiler_id": boiler.get("id"),
            "boiler_name": boiler.get("name"),
            "station": boiler.get("station"),
            "boiler_type": boiler.get("boilerType"),
            "steam_flow": params.get("steam_flow_tph")
            or (params.get("steam", {}) or {}).get("power_tph"),
            "superheated_pressure": params.get("superheated_pressure_mpa")
            or params.get("superheated_pressure_kgf_cm2"),
            "superheated_temp": params.get("superheated_temp"),
            "secondary_pressure": (params.get("secondary_steam", {}) or {}).get("pressure_in_kgf_cm2"),
            "secondary_temp": (params.get("secondary_steam", {}) or {}).get("temperature_out"),
            "fuel": params.get("fuel"),
            "notes": boiler.get("notes"),
        }
        rows.append(row)
    return rows


def main() -> None:
    st.title("База поверхностей нагрева")
    st.write(
        "Гибкий поиск: вводи станцию, тип котла, марку стали или любой текст — таблица адаптируется и показывает котлы, параметры и поверхности."
    )

    data = load_data()
    flattened = flatten_surfaces(data)
    boiler_table = build_boiler_table(data)

    stations = collect_unique(flattened, "station")
    station_selection = st.sidebar.multiselect("Станция", stations, default=stations)
    boiler_types = collect_unique(flattened, "boiler_type")
    type_selection = st.sidebar.multiselect("Тип котла", boiler_types, default=boiler_types)
    steel_set: Set[str] = set()
    for row in flattened:
        steel_value = row.get("steel")
        if isinstance(steel_value, (list, tuple)):
            for piece in steel_value:
                if piece:
                    steel_set.add(str(piece))
        elif steel_value:
            steel_set.add(str(steel_value))
    steel_types = sorted(steel_set)
    steel_selection = st.sidebar.multiselect("Марка стали", steel_types)
    categories = collect_unique(flattened, "category")
    category_selection = st.sidebar.multiselect("Категория", categories, default=categories)
    systems = collect_unique(flattened, "system")
    system_selection = st.sidebar.multiselect("Тракт", systems, default=systems)

    query = st.sidebar.text_input("Свободный поиск", value="")

    def row_matches(row: Dict) -> bool:
        if station_selection and row.get("station") not in station_selection:
            return False
        if type_selection and row.get("boiler_type") not in type_selection:
            return False
        if steel_selection and row.get("steel") not in steel_selection:
            return False
        if category_selection and row.get("category") not in category_selection:
            return False
        if system_selection and row.get("system") not in system_selection:
            return False
        if query and not match_query(row, query):
            return False
        return True

    filtered = [row for row in flattened if row_matches(row)]

    st.sidebar.markdown("---")
    st.sidebar.metric("Котлы в выборке", len({row["boiler_id"] for row in filtered}))
    st.sidebar.metric("Поверхностей в выборке", len(filtered))

    tabs = st.tabs(["Поверхности", "Котлы и станции", "Марки сталей"])

    with tabs[0]:
        if filtered:
            st.dataframe(pd.DataFrame(filtered).fillna("").reindex(columns=SURFACE_COLUMNS))
            csv = pd.DataFrame(filtered).to_csv(index=False).encode("utf-8")
            st.download_button("Скачать выборку поверхностей (CSV)", csv, "surfaces.csv", "text/csv")
        else:
            st.info("Совпадений нет — расширьте фильтры или используйте свободный поиск")

    with tabs[1]:
        station_rows = []
        for boiler in boiler_table:
            if station_selection and boiler.get("station") not in station_selection:
                continue
            if type_selection and boiler.get("boiler_type") not in type_selection:
                continue
            station_rows.append(
                {
                    "station": boiler.get("station"),
                    "boiler_id": boiler.get("boiler_id"),
                    "boiler_type": boiler.get("boiler_type"),
                    "steam_flow": boiler.get("steam_flow"),
                    "superheated_pressure": boiler.get("superheated_pressure"),
                    "superheated_temp": boiler.get("superheated_temp"),
                    "fuel": boiler.get("fuel"),
                    "notes": boiler.get("notes"),
                }
            )
        if station_rows:
            st.dataframe(pd.DataFrame(station_rows).fillna(""))
        else:
            st.info("По выбранным фильтрам нет котлов")

    with tabs[2]:
        steel_rows = []
        for steel in steel_types:
            count = sum(1 for row in flattened if row.get("steel") == steel)
            boilers = sorted({row["boiler_id"] for row in flattened if row.get("steel") == steel})
            steel_rows.append({"steel": steel, "count": count, "boilers": ", ".join(boilers)})
        if steel_rows:
            st.dataframe(pd.DataFrame(steel_rows))
        else:
            st.info("Не удалось собрать список марок стали")

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

    st.subheader("Администрирование данных")
    if st.button("Удалить текущую базу"):
        if DATA_PATH.exists():
            DATA_PATH.unlink()
            data = {"boilers": []}
            st.success("Файл `boilers_reference.json` удалён. Можешь загрузить новую базу через форму выше.")
        else:
            st.warning("Файл уже отсутствует")

    st.header("Исходные данные")
    with st.expander("Посмотреть JSON-структуру базы"):  # noqa: SIM101
        st.json(data)


if __name__ == "__main__":
    main()
