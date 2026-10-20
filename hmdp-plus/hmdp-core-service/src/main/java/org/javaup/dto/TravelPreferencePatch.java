package org.javaup.dto;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonSetter;
import jakarta.validation.constraints.*;
import lombok.Getter;

import java.math.BigDecimal;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** A partial update: missing fields are preserved; explicit null clears a scalar. */
@Getter
public class TravelPreferencePatch {
    @Size(max = 40)
    private String defaultCity;
    @DecimalMin("0") @DecimalMax("100000")
    private BigDecimal budgetPerPerson;
    @Size(max = 12)
    private List<@NotBlank @Size(max = 60) String> cuisines;
    @Size(max = 12)
    private List<@NotBlank @Size(max = 60) String> dietaryNotes;
    @Pattern(regexp = "^(driving|walking)$")
    private String transport;
    @JsonIgnore
    private final Set<String> provided = new HashSet<>();

    @JsonSetter("default_city")
    public void setDefaultCity(String value) { defaultCity = value; provided.add("default_city"); }
    @JsonSetter("budget_per_person")
    public void setBudgetPerPerson(BigDecimal value) { budgetPerPerson = value; provided.add("budget_per_person"); }
    @JsonSetter("cuisines")
    public void setCuisines(List<String> value) { cuisines = value; provided.add("cuisines"); }
    @JsonSetter("dietary_notes")
    public void setDietaryNotes(List<String> value) { dietaryNotes = value; provided.add("dietary_notes"); }
    @JsonSetter("transport")
    public void setTransport(String value) { transport = value; provided.add("transport"); }

    public boolean contains(String field) { return provided.contains(field); }
}
