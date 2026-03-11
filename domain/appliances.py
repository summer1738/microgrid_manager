import json
import os
import uuid
from dataclasses import dataclass, asdict
from typing import List


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "appliances.json")


@dataclass
class Appliance:
    id: str
    name: str
    power_w: float
    priority: int  # 1 = critical, 2 = essential, 3 = non-essential
    manually_shed: bool = False  # user chose to turn this load off


def _ensure_data_dir():
    data_dir = os.path.dirname(DATA_PATH)
    os.makedirs(data_dir, exist_ok=True)


def load_appliances() -> List[Appliance]:
    _ensure_data_dir()
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out = []
    for item in raw:
        if "manually_shed" not in item:
            item = {**item, "manually_shed": False}
        out.append(Appliance(**item))
    return out


def save_appliances(appliances: List[Appliance]) -> None:
    _ensure_data_dir()
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump([asdict(a) for a in appliances], f, indent=2)


def add_appliance(name: str, power_w: float, priority: int) -> Appliance:
    appliances = load_appliances()
    new = Appliance(id=str(uuid.uuid4()), name=name, power_w=power_w, priority=priority)
    appliances.append(new)
    save_appliances(appliances)
    return new


def set_appliance_shed(appliance_id: str, shed: bool) -> bool:
    """Set manually_shed for an appliance. Returns True if found and updated."""
    appliances = load_appliances()
    for a in appliances:
        if a.id == appliance_id:
            a.manually_shed = shed
            save_appliances(appliances)
            return True
    return False


def get_appliance(appliance_id: str):
    """Return appliance by id or None."""
    for a in load_appliances():
        if a.id == appliance_id:
            return a
    return None


def delete_appliance(appliance_id: str) -> bool:
    appliances = load_appliances()
    new_list = [a for a in appliances if a.id != appliance_id]
    if len(new_list) == len(appliances):
        return False
    save_appliances(new_list)
    return True

