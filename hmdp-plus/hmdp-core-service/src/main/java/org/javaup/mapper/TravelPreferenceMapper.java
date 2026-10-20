package org.javaup.mapper;

import org.apache.ibatis.annotations.*;
import org.javaup.entity.TravelPreference;

public interface TravelPreferenceMapper {
    String COLUMNS = "user_id AS userId,default_city AS defaultCity,budget_per_person AS budgetPerPerson,"
            + "cuisines_json AS cuisinesJson,dietary_notes_json AS dietaryNotesJson,transport";

    @Select("SELECT " + COLUMNS + " FROM tb_travel_preference WHERE user_id=#{userId}")
    TravelPreference find(@Param("userId") Long userId);

    @Insert("INSERT INTO tb_travel_preference(user_id,cuisines_json,dietary_notes_json) "
            + "VALUES(#{userId},'[]','[]') ON DUPLICATE KEY UPDATE revision=revision")
    int ensure(@Param("userId") Long userId);

    @Select("SELECT " + COLUMNS + " FROM tb_travel_preference WHERE user_id=#{userId} FOR UPDATE")
    TravelPreference lock(@Param("userId") Long userId);

    @Update("UPDATE tb_travel_preference SET default_city=#{defaultCity},budget_per_person=#{budgetPerPerson},"
            + "cuisines_json=#{cuisinesJson},dietary_notes_json=#{dietaryNotesJson},transport=#{transport},"
            + "revision=revision+1 WHERE user_id=#{userId}")
    int update(TravelPreference preference);
}
