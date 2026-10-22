from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


SkillName = Literal["visit-review", "plan-city-trip", "explore-food", "plan-relaxed-half-day", "budget-city-day", "family-slow-trip", "rainy-day-plan", "voucher-check", "arrival-first-stop", "replan-remaining"]
ROOT = Path(__file__).parent / "bundled"
# Only these server-owned paths can be loaded; never accept file paths from a model.
CATALOG = (
    {"name": "visit-review", "title": "去过之后", "description": "回顾用户记录的到店体验和实际消费，引导保存私有反馈与可编辑探店草稿；经本人确认后再保存长期偏好或到发布页公开。"},
    {"name": "plan-city-trip", "title": "多日行程规划", "description": "按城市、1至7天天数、人数、全程总预算和偏好规划每日安排，查询真实地点并由高德计算站点间路线，校验每天时间、保存可调整行程卡。"},
    {"name": "arrival-first-stop", "title": "到站第一程", "description": "从车站或酒店开始，核对同名地点、抵达时间与行李需求，查询第一站和步行或驾车路线。"},
    {"name": "replan-remaining", "title": "随心改行程", "description": "遇到闭店、疲劳或临时变更，读取最新行程，只调整未完成站点，比较路线后按意愿保存。"},
    {"name": "budget-city-day", "title": "预算一日游", "description": "区分人均与总预算，核算餐饮已知费用与交通、门票未知项，规划少折返的一日出游。"},
    {"name": "family-slow-trip", "title": "亲子慢游", "description": "带孩子或长辈出行，先确认体力、休息和同行需求，查询地点并减少步行；不猜无障碍设施。"},
    {"name": "rainy-day-plan", "title": "雨天备选", "description": "用户提供下雨或高温条件时，查询室内候选并调整未完成行程；不提供未经查询的实时天气。"},
    {"name": "voucher-check", "title": "优惠券核查", "description": "核对平台优惠券购买价、面值、有效期与使用限制，说明未知条件；不抢券、不下单。"},
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
