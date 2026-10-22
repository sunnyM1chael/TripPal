package org.javaup.workshop;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.util.List;

public final class WorkshopModels {
    private WorkshopModels() {}
    public record Stop(
        @NotBlank @Size(max=80) String name,
        @NotBlank @Size(max=200) String address,
        @NotBlank @Pattern(regexp="FOOD|PLAY") String kind,
        @NotBlank @Size(max=1000) String advice,
        @NotNull @DecimalMin("-180") @DecimalMax("180") BigDecimal longitude,
        @NotNull @DecimalMin("-90") @DecimalMax("90") BigDecimal latitude,
        @NotNull @Min(5) @Max(1440) Integer minutes,
        @NotNull @DecimalMin("0") @DecimalMax("100000") BigDecimal cost) {}
    public record WorkInput(
        @NotBlank @Size(max=80) String title,
        @NotBlank @Size(max=40) String city,
        @NotBlank @Pattern(regexp="FOOD|PLAY") String theme,
        @NotBlank @Size(max=2000) String description,
        @Size(max=100) String audience,
        boolean allowRemix,
        @NotBlank @Pattern(regexp="DRAFT|PUBLISHED") String status,
        @Min(0) int version,
        @Size(max=36) String sourceId,
        @Size(max=300) String changeNote,
        @NotEmpty @Size(max=20) List<@NotNull @Valid Stop> stops) {}
    public record Work(String id, String authorId, String authorName, int version,
                       String updatedAt, WorkInput content) {}
    public record Trip(String id, String workId, Work snapshot, List<Stop> stops,
                       List<Integer> completed, int version) {}
    public record TripInput(@NotEmpty @Size(max=20) List<@NotNull @Valid Stop> stops,
                            @NotNull @Size(max=20) List<@NotNull @Min(0) Integer> completed,
                            @Min(0) int version) {}
    public record FeedbackInput(@NotBlank @Size(max=36) String tripId,
        @Min(0) @Max(19) int stopIndex,
        @NotBlank @Pattern(regexp="WORTH|OK|AVOID|CORRECTION") String verdict,
        @Size(max=1000) String note,
        @DecimalMin("0") @DecimalMax("100000") BigDecimal actualCost) {}
    public record Feedback(String id, String authorName, String stopName, String verdict,
                           String note, BigDecimal actualCost, String createdAt) {}
}
