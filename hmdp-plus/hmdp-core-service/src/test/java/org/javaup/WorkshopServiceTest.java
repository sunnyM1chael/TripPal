package org.javaup;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.javaup.workshop.*;
import org.javaup.utils.UserHolder;
import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.web.server.ResponseStatusException;
import jakarta.validation.Validation;
import java.nio.file.*;
import java.math.BigDecimal;
import java.util.*;
import static org.javaup.workshop.WorkshopModels.*;
import static org.junit.jupiter.api.Assertions.*;

class WorkshopServiceTest {
    WorkshopService service;
    JdbcTemplate db;
    Stop stop=new Stop("小店","城中路1号","FOOD","推荐招牌早餐",new BigDecimal("118.7"),new BigDecimal("32.0"),40,new BigDecimal("25"));
    @BeforeEach void setup() throws Exception {
        db=new JdbcTemplate(new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa",""));
        String ddl=Files.readString(Path.of("../sql/3_city_workshop.sql")).replaceAll("(?m)^--.*$","").replace(" ENGINE=InnoDB DEFAULT CHARSET=utf8mb4","");
        for(String sql:ddl.split(";")) if(!sql.isBlank()) db.execute(sql);
        service=new WorkshopService(db,new ObjectMapper());
    }
    @AfterEach void clean(){UserHolder.removeUser();if(db!=null)db.execute("DROP ALL OBJECTS");}
    WorkInput input(String status,boolean remix,String source,int version){return new WorkInput("早餐小店","南京","FOOD","亲自吃过的早餐","朋友",remix,status,version,source,source==null?"":"替换早餐站",List.of(stop));}
    @Test void draftPrivateAndWritesOwned(){
        Work w=service.create(1,"作者",input("DRAFT",true,null,0));
        assertThrows(ResponseStatusException.class,()->service.get(w.id(),2L));
        assertThrows(ResponseStatusException.class,()->service.update(2,w.id(),input("PUBLISHED",true,null,0)));
        assertTrue(service.discover("南京","FOOD",1).isEmpty());
        assertEquals(w.id(),service.get(w.id(),1L).id());
    }
    @Test void snapshotIdempotencyAndCrossUserIsolation(){
        Work w=service.create(1,"作者",input("PUBLISHED",true,null,0));
        Trip t=service.join(2,w.id());
        service.update(1,w.id(),input("DRAFT",false,null,0));
        assertEquals("PUBLISHED",service.trips(2).get(0).snapshot().content().status());
        assertTrue(service.trips(3).isEmpty());
        assertThrows(ResponseStatusException.class,()->service.updateTrip(3,t.id(),new TripInput(t.stops(),List.of(0),0)));
        service.update(1,w.id(),input("PUBLISHED",true,null,1));
        assertEquals(t.id(),service.join(2,w.id()).id());
        assertEquals(0,service.join(2,w.id()).snapshot().version());
    }
    @Test void staleAuthorAndTripUpdatesConflict(){
        Work w=service.create(1,"作者",input("PUBLISHED",true,null,0));
        service.update(1,w.id(),input("PUBLISHED",true,null,0));
        assertEquals(409,assertThrows(ResponseStatusException.class,()->service.update(1,w.id(),input("PUBLISHED",true,null,0))).getStatusCode().value());
        Trip t=service.join(2,w.id());
        service.updateTrip(2,t.id(),new TripInput(t.stops(),List.of(0),0));
        assertEquals(409,assertThrows(ResponseStatusException.class,()->service.updateTrip(2,t.id(),new TripInput(t.stops(),List.of(),0))).getStatusCode().value());
    }
    @Test void remixChecksPermissionAndCannotForgeSourceOnUpdate(){
        Work w=service.create(1,"作者",input("PUBLISHED",false,null,0));
        assertThrows(ResponseStatusException.class,()->service.create(2,"读者",input("PUBLISHED",true,w.id(),0)));
        service.update(1,w.id(),input("PUBLISHED",true,null,0));
        Work remix=service.create(2,"读者",input("DRAFT",true,w.id(),0));
        assertThrows(ResponseStatusException.class,()->service.update(2,remix.id(),input("PUBLISHED",true,null,0)));
        service.update(1,w.id(),input("DRAFT",false,null,1));
        assertThrows(ResponseStatusException.class,()->service.update(2,remix.id(),input("PUBLISHED",true,w.id(),0)));
    }
    @Test void feedbackRequiresOwnedCompletedStopAndRetriesUpdate(){
        Work w=service.create(1,"作者",input("PUBLISHED",true,null,0)); Trip t=service.join(2,w.id());
        FeedbackInput f=new FeedbackInput(t.id(),0,"WORTH","好吃",BigDecimal.TEN);
        assertThrows(ResponseStatusException.class,()->service.feedback(2,"游客",f));
        service.updateTrip(2,t.id(),new TripInput(t.stops(),List.of(0),0));
        assertThrows(ResponseStatusException.class,()->service.feedback(3,"其他人",f));
        service.feedback(2,"游客",f); service.feedback(2,"游客",new FeedbackInput(t.id(),0,"OK","更新",BigDecimal.ONE));
        assertEquals(1,service.feedbacks(w.id(),null).size()); assertEquals("OK",service.feedbacks(w.id(),null).get(0).verdict());
        assertThrows(ResponseStatusException.class,()->service.feedback(2,"游客",new FeedbackInput(t.id(),0,"CORRECTION","",null)));
    }
    @Test void malformedCompletionAndChangingVisitedStationRejected(){
        Work w=service.create(1,"作者",input("PUBLISHED",true,null,0)); Trip t=service.join(2,w.id());
        assertThrows(ResponseStatusException.class,()->service.updateTrip(2,t.id(),new TripInput(t.stops(),List.of(1),0)));
        assertThrows(ResponseStatusException.class,()->service.updateTrip(2,t.id(),new TripInput(t.stops(),List.of(0,0),0)));
        service.updateTrip(2,t.id(),new TripInput(t.stops(),List.of(0),0));
        assertThrows(ResponseStatusException.class,()->service.updateTrip(2,t.id(),new TripInput(List.of(stop,stop),List.of(0),1)));
    }
    @Test void bookmarkIsIdempotentAndWithdrawalHidesIt(){
        Work w=service.create(1,"作者",input("PUBLISHED",true,null,0));
        service.save(2,w.id(),true);service.save(2,w.id(),true);assertEquals(1,service.saved(2).size());
        service.update(1,w.id(),input("DRAFT",true,null,0));assertTrue(service.saved(2).isEmpty());
        service.save(2,w.id(),false);assertEquals(0,db.queryForObject("SELECT COUNT(*) FROM tb_city_save",Integer.class));
    }
    @Test void controllerRejectsAnonymousPersonalEndpoints(){
        WorkshopController c=new WorkshopController(service);
        assertEquals(401,assertThrows(ResponseStatusException.class,c::mine).getStatusCode().value());
        assertThrows(ResponseStatusException.class,c::trips);assertThrows(ResponseStatusException.class,c::saved);
        assertThrows(ResponseStatusException.class,()->c.create(input("PUBLISHED",true,null,0)));
    }
    @Test void validationRejectsEmptyAndNullStops(){
        try(var factory=Validation.buildDefaultValidatorFactory()){
            var v=factory.getValidator(); assertTrue(v.validate(input("PUBLISHED",true,null,0)).isEmpty());
            WorkInput bad=new WorkInput("","南京","FOOD","介绍","",true,"PUBLISHED",0,null,"",Arrays.asList((Stop)null));
            assertFalse(v.validate(bad).isEmpty());
        }
    }
}
