package org.javaup.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Data
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class TravelPreferenceView {
    private String defaultCity;
    private BigDecimal budgetPerPerson;
    private List<String> cuisines = new ArrayList<>();
    private List<String> dietaryNotes = new ArrayList<>();
    private String transport;
}
