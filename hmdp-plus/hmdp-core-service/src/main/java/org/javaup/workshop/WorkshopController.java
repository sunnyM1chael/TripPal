package org.javaup.workshop;

import jakarta.validation.Valid;
import org.javaup.dto.Result;
import org.javaup.utils.UserHolder;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.server.ResponseStatusException;
import java.util.List;
import static org.javaup.workshop.WorkshopModels.*;

@RestController
@RequestMapping("/workshop")
public class WorkshopController {
    private final WorkshopService service;
    public WorkshopController(WorkshopService service){this.service=service;}
    private Long viewer(){return UserHolder.getUser()==null?null:UserHolder.getUser().getId();}
    private long user(){Long id=viewer();if(id==null)throw new ResponseStatusException(HttpStatus.UNAUTHORIZED,"请先登录");return id;}
    private String name(){user();return UserHolder.getUser().getNickName()==null?"旅行者":UserHolder.getUser().getNickName();}
    @GetMapping("/works") public Result<List<Work>> discover(@RequestParam("city") String city,@RequestParam(value="theme", defaultValue="FOOD") String theme,@RequestParam(value="page", defaultValue="1") int page){return Result.ok(service.discover(city,theme,page));}
    @GetMapping("/works/{id}") public Result<Work> get(@PathVariable("id") String id){return Result.ok(service.get(id,viewer()));}
    @GetMapping("/mine") public Result<List<Work>> mine(){return Result.ok(service.mine(user()));}
    @PostMapping("/works") public Result<Work> create(@Valid @RequestBody WorkInput input){return Result.ok(service.create(user(),name(),input));}
    @PutMapping("/works/{id}") public Result<Work> update(@PathVariable("id") String id,@Valid @RequestBody WorkInput input){return Result.ok(service.update(user(),id,input));}
    @GetMapping("/saved") public Result<List<Work>> saved(){return Result.ok(service.saved(user()));}
    @PutMapping("/works/{id}/saved") public Result<Void> save(@PathVariable("id") String id){service.save(user(),id,true);return Result.ok();}
    @DeleteMapping("/works/{id}/saved") public Result<Void> unsave(@PathVariable("id") String id){service.save(user(),id,false);return Result.ok();}
    @PostMapping("/works/{id}/trips") public Result<Trip> join(@PathVariable("id") String id){return Result.ok(service.join(user(),id));}
    @GetMapping("/trips") public Result<List<Trip>> trips(){return Result.ok(service.trips(user()));}
    @PutMapping("/trips/{id}") public Result<Trip> updateTrip(@PathVariable("id") String id,@Valid @RequestBody TripInput input){return Result.ok(service.updateTrip(user(),id,input));}
    @PostMapping("/feedback") public Result<Void> feedback(@Valid @RequestBody FeedbackInput input){service.feedback(user(),name(),input);return Result.ok();}
    @GetMapping("/works/{id}/feedback") public Result<List<Feedback>> feedbacks(@PathVariable("id") String id){return Result.ok(service.feedbacks(id,viewer()));}
    @ExceptionHandler(org.springframework.web.bind.MethodArgumentNotValidException.class)
    public ResponseEntity<Result<Void>> invalid(org.springframework.web.bind.MethodArgumentNotValidException e) {
        var first=e.getBindingResult().getFieldErrors().stream().findFirst();
        return ResponseEntity.badRequest().body(Result.fail(first.map(f->f.getField()+": "+f.getDefaultMessage()).orElse("请检查填写内容")));
    }
    @ExceptionHandler(ResponseStatusException.class) public ResponseEntity<Result<Void>> error(ResponseStatusException e){return ResponseEntity.status(e.getStatusCode()).body(Result.fail(e.getReason()));}
}
