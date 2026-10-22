package org.javaup.workshop;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
import java.util.*;
import static org.javaup.workshop.WorkshopModels.*;

@Service
public class WorkshopService {
    private final JdbcTemplate db;
    private final ObjectMapper json;
    public WorkshopService(JdbcTemplate db, ObjectMapper json) { this.db=db; this.json=json; }
    private final RowMapper<Work> workMapper = (r,n) -> new Work(r.getString("id"),
        r.getString("author_id"), r.getString("author_name"), r.getInt("version"),
        r.getString("updated_at"), read(r.getString("content"), new TypeReference<WorkInput>() {}));
    private final RowMapper<Trip> tripMapper = (r,n) -> new Trip(r.getString("id"), r.getString("work_id"),
        read(r.getString("snapshot"), new TypeReference<Work>() {}),
        read(r.getString("stops"), new TypeReference<List<Stop>>() {}),
        read(r.getString("completed"), new TypeReference<List<Integer>>() {}), r.getInt("version"));

    public List<Work> discover(String city, String theme, int page) {
        if (city==null || city.isBlank() || city.length()>40 || theme==null
            || !Set.of("FOOD","PLAY").contains(theme) || page<1 || page>500)
            throw bad("请选择城市和吃玩主题，页码需在 1–500 之间");
        return db.query("SELECT * FROM tb_city_work WHERE city=? AND theme=? AND status='PUBLISHED' ORDER BY updated_at DESC,id DESC LIMIT 20 OFFSET ?",
            workMapper,city.trim(),theme,(page-1)*20);
    }
    public List<Work> mine(long user) {
        return db.query("SELECT * FROM tb_city_work WHERE author_id=? ORDER BY updated_at DESC LIMIT 100",workMapper,user);
    }
    public Work get(String id, Long viewer) {
        var rows=db.query("SELECT * FROM tb_city_work WHERE id=?",workMapper,id);
        if(rows.isEmpty()) throw missing();
        Work w=rows.get(0);
        if(!w.content().status().equals("PUBLISHED") && !w.authorId().equals(String.valueOf(viewer))) throw missing();
        return w;
    }
    @Transactional
    public Work create(long user,String name,WorkInput input) {
        if(hasSource(input)) {
            // Serialize permission changes with creation of a public derivative.
            Work source=lockWork(input.sourceId());
            if(!source.content().status().equals("PUBLISHED") || !source.content().allowRemix())
                throw bad("原作品未公开或未允许改编");
            if(input.changeNote()==null || input.changeNote().isBlank()) throw bad("请说明改编了什么");
        }
        String id=UUID.randomUUID().toString();
        db.update("INSERT INTO tb_city_work (id,author_id,author_name,city,theme,status,source_id,content,version) VALUES (?,?,?,?,?,?,?,?,0)",
            id,user,name,input.city().trim(),input.theme(),input.status(),input.sourceId(),write(input));
        return get(id,user);
    }
    @Transactional
    public Work update(long user,String id,WorkInput input) {
        Work old=lockWork(id);
        if(!old.authorId().equals(String.valueOf(user))) throw missing();
        if(!Objects.equals(old.content().sourceId(),input.sourceId())) throw bad("不能修改作品来源");
        if(hasSource(input)) {
            if(input.changeNote()==null || input.changeNote().isBlank()) throw bad("请保留改编说明");
            if(input.status().equals("PUBLISHED") && !old.content().status().equals("PUBLISHED")) {
                Work source=lockWork(input.sourceId());
                if(!source.content().status().equals("PUBLISHED") || !source.content().allowRemix()) throw bad("来源已撤回改编权限");
            }
        }
        int changed=db.update("UPDATE tb_city_work SET city=?,theme=?,status=?,content=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND author_id=? AND version=?",
            input.city().trim(),input.theme(),input.status(),write(input),id,user,input.version());
        if(changed!=1) throw conflict();
        return get(id,user);
    }
    private boolean hasSource(WorkInput input) { return input.sourceId()!=null && !input.sourceId().isBlank(); }
    private Work lockWork(String id) {
        var rows=db.query("SELECT * FROM tb_city_work WHERE id=? FOR UPDATE",workMapper,id);
        if(rows.isEmpty()) throw missing(); return rows.get(0);
    }
    public List<Work> saved(long user) {
        return db.query("SELECT w.* FROM tb_city_work w INNER JOIN tb_city_save s ON w.id=s.work_id WHERE s.user_id=? AND w.status='PUBLISHED' ORDER BY w.updated_at DESC LIMIT 100",workMapper,user);
    }
    public void save(long user,String id,boolean saved) {
        if(!saved) { db.update("DELETE FROM tb_city_save WHERE user_id=? AND work_id=?",user,id); return; }
        Work w=get(id,user);
        if(!w.content().status().equals("PUBLISHED")) throw bad("只能收藏已发布作品");
        db.update("INSERT INTO tb_city_save (user_id,work_id) VALUES (?,?) ON DUPLICATE KEY UPDATE work_id=VALUES(work_id)",user,id);
    }
    @Transactional
    public Trip join(long user,String id) {
        Work w=get(id,user);
        if(!w.content().status().equals("PUBLISHED")) throw bad("只能使用已发布作品");
        // Unique user/work key preserves personal changes when a request is retried.
        db.update("INSERT INTO tb_city_trip (id,user_id,work_id,snapshot,stops,completed) VALUES (?,?,?,?,?,?) ON DUPLICATE KEY UPDATE work_id=VALUES(work_id)",
            UUID.randomUUID().toString(),user,id,write(w),write(w.content().stops()),"[]");
        return db.query("SELECT * FROM tb_city_trip WHERE user_id=? AND work_id=?",tripMapper,user,id).get(0);
    }
    public List<Trip> trips(long user) {
        return db.query("SELECT * FROM tb_city_trip WHERE user_id=? ORDER BY created_at DESC LIMIT 100",tripMapper,user);
    }
    private Trip trip(long user,String id,boolean lock) {
        var rows=db.query("SELECT * FROM tb_city_trip WHERE id=? AND user_id=?"+(lock?" FOR UPDATE":""),tripMapper,id,user);
        if(rows.isEmpty()) throw missing(); return rows.get(0);
    }
    @Transactional
    public Trip updateTrip(long user,String id,TripInput input) {
        Trip old=trip(user,id,true);
        if(new HashSet<>(input.completed()).size()!=input.completed().size()
            || input.completed().stream().anyMatch(i->i<0 || i>=input.stops().size())) throw bad("打卡站点无效");
        if(!old.stops().equals(input.stops()) && (!old.completed().isEmpty()
            || db.queryForObject("SELECT COUNT(*) FROM tb_city_feedback WHERE trip_id=?",Integer.class,id)>0))
            throw bad("已开始打卡的行程不能修改站点");
        int changed=db.update("UPDATE tb_city_trip SET stops=?,completed=?,version=version+1 WHERE id=? AND user_id=? AND version=?",
            write(input.stops()),write(input.completed()),id,user,input.version());
        if(changed!=1) throw conflict(); return trip(user,id,false);
    }
    @Transactional
    public void feedback(long user,String name,FeedbackInput input) {
        Trip t=trip(user,input.tripId(),true);
        if(input.stopIndex()>=t.stops().size() || !t.completed().contains(input.stopIndex())) throw bad("请先标记本站去过");
        if(input.verdict().equals("CORRECTION") && (input.note()==null || input.note().isBlank())) throw bad("请填写需要纠正的信息");
        db.update("INSERT INTO tb_city_feedback (id,user_id,author_name,work_id,trip_id,stop_index,stop_name,verdict,note,actual_cost) VALUES (?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE verdict=VALUES(verdict),note=VALUES(note),actual_cost=VALUES(actual_cost),created_at=CURRENT_TIMESTAMP",
            UUID.randomUUID().toString(),user,name,t.workId(),t.id(),input.stopIndex(),t.stops().get(input.stopIndex()).name(),input.verdict(),input.note(),input.actualCost());
    }
    public List<Feedback> feedbacks(String id,Long viewer) {
        get(id,viewer);
        return db.query("SELECT * FROM tb_city_feedback WHERE work_id=? ORDER BY created_at DESC LIMIT 100",
            (r,n)->new Feedback(r.getString("id"),r.getString("author_name"),r.getString("stop_name"),r.getString("verdict"),r.getString("note"),r.getBigDecimal("actual_cost"),r.getString("created_at")),id);
    }
    private String write(Object value) {
        try {return json.writeValueAsString(value);} catch(JsonProcessingException e){throw new IllegalStateException(e);}
    }
    private <T>T read(String value,TypeReference<T> type) {
        try {return json.readValue(value,type);} catch(JsonProcessingException e){throw new IllegalStateException(e);}
    }
    private static ResponseStatusException bad(String message){return new ResponseStatusException(HttpStatus.BAD_REQUEST,message);}
    private static ResponseStatusException missing(){return new ResponseStatusException(HttpStatus.NOT_FOUND,"内容不存在或无权访问");}
    private static ResponseStatusException conflict(){return new ResponseStatusException(HttpStatus.CONFLICT,"内容已更新，请刷新后重试");}
}
