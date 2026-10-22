from app.itineraries.models import CreateItinerary, EditItinerary
from app.tools.travel import NoArguments


DEFINITIONS = {
    "get_visit_feedback": (NoArguments, "读取本轮选定行程中用户自己记录的已完成地点体验与私有草稿。只代表用户自述，不是平台评分。记录或修改反馈请引导到我的行程中已完成站点的体验表单；不能代用户确认去过或公开发布。"),
    "create_itinerary": (CreateItinerary, "生成并保存可编辑行程卡，服务端重新查询真实地点和高德路线。单城市1至7天，day_count指定天数，stops按day和当天顺序排列，多日每天最多4站。start_time/end_time为每天时间窗口，rest_minutes为每天额外休息；budget_yuan为全程所有人的总预算。只用已搜索到的poi_id，不猜价格；一次请求最多创建一份。"),
    "get_current_itinerary": (NoArguments, "读取本轮选定行程的最新版本和地点ID，调整前先读取。未选定时请用户打开行程卡再继续。"),
    "edit_current_itinerary": (EditItinerary, "修改本轮选定行程：换店、删点、调整顺序/停留、标记完成或刷新路线。先读取版本和stop_id，只按用户当前要求操作，已完成部分不能修改。"),
}
