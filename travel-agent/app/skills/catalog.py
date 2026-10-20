from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


SkillName = Literal["explore-food", "plan-relaxed-half-day"]
ROOT = Path(__file__).parent / "bundled"
# Only these server-owned paths can be loaded; never accept file paths from a model.
CATALOG = (
    {"name": "explore-food", "title": "美食探索",
     "description": "按城市、口味和预算比较餐馆，查询平台优惠券；适用于找店、吃什么、本地特色和美食探索。"},
    {"name": "plan-relaxed-half-day", "title": "轻松半日游",
     "description": "安排半天或几小时的轻松出游，核对地点与路线，预留休息；适用于下午逛逛、别太累、少走路。"},
)


class LoadSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: SkillName


def catalog() -> list[dict]:
    return [dict(item) for item in CATALOG]


def load_skill(name: str) -> str:
    if name not in {item["name"] for item in CATALOG}:
        raise ValueError("Unknown travel skill")
    text = (ROOT / name / "SKILL.md").read_text(encoding="utf-8")
    header, body = text.split("\n---\n", 1)
    if not header.startswith("---\n") or f"name: {name}\n" not in header + "\n":
        raise ValueError("Invalid bundled skill metadata")
    if not body.strip() or len(text) > 12000:
        raise ValueError("Invalid bundled skill body")
    return body.strip()


def loader_schema() -> dict:
    return {"type": "function", "function": {
        "name": "load_travel_skill",
        "description": "按任务加载一个旅行技能。新任务匹配目录时，先单独调用此工具，再按加载的流程查询业务工具。",
        "parameters": LoadSkill.model_json_schema(),
    }}
