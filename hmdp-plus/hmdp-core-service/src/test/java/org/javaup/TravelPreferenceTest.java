package org.javaup;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.javaup.controller.TravelPreferenceController;
import org.javaup.dto.TravelPreferencePatch;
import org.javaup.dto.UserDTO;
import org.javaup.entity.TravelPreference;
import org.javaup.mapper.TravelPreferenceMapper;
import org.javaup.service.TravelPreferenceService;
import org.javaup.utils.UserHolder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.*;

class TravelPreferenceTest {
    private final ObjectMapper json = new ObjectMapper();
    private final FakeMapper mapper = new FakeMapper();
    private final TravelPreferenceService service = new TravelPreferenceService(mapper, json);

    @AfterEach void cleanup() { UserHolder.removeUser(); }

    @Test void partialPatchPreservesMissingFieldsAndExplicitNullClears() throws Exception {
        TravelPreference row = new TravelPreference();
        row.setUserId(7L);
        row.setDefaultCity("南京");
        row.setBudgetPerPerson(new BigDecimal("100.00"));
        row.setCuisinesJson("[\"淮扬菜\"]");
        row.setDietaryNotesJson("[]");
        mapper.row = row;
        var patch = json.readValue("{\"budget_per_person\":null,\"dietary_notes\":[\"不吃辣\",\" 不吃辣 \" ]}", TravelPreferencePatch.class);
        var result = service.patch(7L, patch);
        assertNull(result.getBudgetPerPerson());
        assertEquals("南京", result.getDefaultCity());
        assertEquals(1, result.getDietaryNotes().size());
        assertEquals("淮扬菜", result.getCuisines().get(0));
        assertEquals(7L, mapper.lastUserId);
        assertSame(row, mapper.row);
    }

    @Test void controllerAlwaysUsesAuthenticatedUser() throws Exception {
        var controller = new TravelPreferenceController(service);
        assertEquals(401, controller.get().getStatusCode().value());
        assertNull(mapper.lastUserId);
        UserDTO user = new UserDTO();
        user.setId(9L);
        UserHolder.saveUser(user);
        var patch = json.readValue("{\"default_city\":\"苏州\"}", TravelPreferencePatch.class);
        controller.patch(patch);
        controller.clear();
        assertEquals(9L, mapper.lastUserId);
        assertNull(service.get(9L).getDefaultCity());
    }
    private static class FakeMapper implements TravelPreferenceMapper {
        TravelPreference row;
        Long lastUserId;
        public TravelPreference find(Long id) { lastUserId = id; return row; }
        public int ensure(Long id) {
            lastUserId = id;
            if (row == null) {
                row = new TravelPreference();
                row.setUserId(id);
                row.setCuisinesJson("[]");
                row.setDietaryNotesJson("[]");
            }
            return 1;
        }
        public TravelPreference lock(Long id) { lastUserId = id; return row; }
        public int update(TravelPreference value) { row = value; lastUserId = value.getUserId(); return 1; }
    }
}
