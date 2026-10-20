package org.javaup.entity;

import lombok.Data;
import java.math.BigDecimal;

/** Business-owned preferences. Never stores chat transcripts or access tokens. */
@Data
public class TravelPreference {
    private Long userId;
    private String defaultCity;
    private BigDecimal budgetPerPerson;
    private String cuisinesJson;
    private String dietaryNotesJson;
    private String transport;
}
