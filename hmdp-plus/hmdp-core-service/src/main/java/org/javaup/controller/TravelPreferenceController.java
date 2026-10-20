package org.javaup.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.javaup.dto.Result;
import org.javaup.dto.TravelPreferencePatch;
import org.javaup.dto.TravelPreferenceView;
import org.javaup.service.TravelPreferenceService;
import org.javaup.utils.UserHolder;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/** Every operation is scoped to the authenticated user; no user ID is accepted from the client. */
@RestController
@RequiredArgsConstructor
@RequestMapping("/user/travel-preferences")
public class TravelPreferenceController {
    private final TravelPreferenceService service;

    @GetMapping
    public ResponseEntity<Result<TravelPreferenceView>> get() {
        if (UserHolder.getUser() == null) return unauthorized();
        return ResponseEntity.ok(Result.ok(service.get(UserHolder.getUser().getId())));
    }

    @PatchMapping
    public ResponseEntity<Result<TravelPreferenceView>> patch(@Valid @RequestBody TravelPreferencePatch patch) {
        if (UserHolder.getUser() == null) return unauthorized();
        return ResponseEntity.ok(Result.ok(service.patch(UserHolder.getUser().getId(), patch)));
    }

    @DeleteMapping
    public ResponseEntity<Result<Void>> clear() {
        if (UserHolder.getUser() == null) return ResponseEntity.status(401).body(Result.fail("请先登录"));
        service.clear(UserHolder.getUser().getId());
        return ResponseEntity.ok(Result.ok());
    }

    private ResponseEntity<Result<TravelPreferenceView>> unauthorized() {
        return ResponseEntity.status(401).body(Result.fail("请先登录"));
    }
}
