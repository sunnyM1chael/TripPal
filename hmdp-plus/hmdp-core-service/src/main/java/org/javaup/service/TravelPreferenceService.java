package org.javaup.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.javaup.dto.TravelPreferencePatch;
import org.javaup.dto.TravelPreferenceView;
import org.javaup.entity.TravelPreference;
import org.javaup.mapper.TravelPreferenceMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.RoundingMode;
import java.util.Collections;
import java.util.List;

@Service
@RequiredArgsConstructor
public class TravelPreferenceService {
    private final TravelPreferenceMapper mapper;
    private final ObjectMapper json;

    public TravelPreferenceView get(Long userId) {
        return view(mapper.find(userId));
    }

    @Transactional(rollbackFor = Exception.class)
    public TravelPreferenceView patch(Long userId, TravelPreferencePatch patch) {
        // Unique user_id plus a row lock serialize concurrent partial updates, including first write.
        mapper.ensure(userId);
        TravelPreference row = mapper.lock(userId);
        if (patch.contains("default_city")) row.setDefaultCity(trim(patch.getDefaultCity()));
        if (patch.contains("budget_per_person")) row.setBudgetPerPerson(patch.getBudgetPerPerson() == null ? null
                : patch.getBudgetPerPerson().setScale(2, RoundingMode.HALF_UP));
        if (patch.contains("cuisines")) row.setCuisinesJson(encode(patch.getCuisines()));
        if (patch.contains("dietary_notes")) row.setDietaryNotesJson(encode(patch.getDietaryNotes()));
        if (patch.contains("transport")) row.setTransport(patch.getTransport());
        mapper.update(row);
        return view(row);
    }

    @Transactional(rollbackFor = Exception.class)
    public void clear(Long userId) {
        mapper.ensure(userId);
        TravelPreference row = mapper.lock(userId);
        row.setDefaultCity(null);
        row.setBudgetPerPerson(null);
        row.setCuisinesJson("[]");
        row.setDietaryNotesJson("[]");
        row.setTransport(null);
        mapper.update(row);
    }

    private TravelPreferenceView view(TravelPreference row) {
        TravelPreferenceView view = new TravelPreferenceView();
        if (row == null) return view;
        view.setDefaultCity(row.getDefaultCity());
        view.setBudgetPerPerson(row.getBudgetPerPerson());
        view.setCuisines(decode(row.getCuisinesJson()));
        view.setDietaryNotes(decode(row.getDietaryNotesJson()));
        view.setTransport(row.getTransport());
        return view;
    }

    private String encode(List<String> values) {
        List<String> normalized = values == null ? Collections.emptyList()
                : values.stream().map(String::trim).distinct().toList();
        try { return json.writeValueAsString(normalized); }
        catch (JsonProcessingException ex) { throw new IllegalStateException("偏好序列化失败", ex); }
    }

    private List<String> decode(String value) {
        if (value == null || value.isBlank()) return Collections.emptyList();
        try { return json.readValue(value, new TypeReference<List<String>>() {}); }
        catch (JsonProcessingException ex) { throw new IllegalStateException("偏好数据格式异常", ex); }
    }

    private String trim(String value) { return value == null || value.isBlank() ? null : value.trim(); }
}
