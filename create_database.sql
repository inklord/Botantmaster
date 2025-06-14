-- Crear la base de datos
CREATE DATABASE IF NOT EXISTS antmaster
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- Usar la base de datos
USE antmaster;

-- Crear tabla de especies
CREATE TABLE IF NOT EXISTS species (
    id INT AUTO_INCREMENT PRIMARY KEY,
    scientific_name VARCHAR(255) NOT NULL,
    antwiki_url TEXT,
    photo_url TEXT,
    inaturalist_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_scientific_name (scientific_name),
    INDEX idx_scientific_name (scientific_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crear tabla temporal de imágenes
CREATE TABLE IF NOT EXISTS species_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    species_id INT NOT NULL,
    inaturalist_id VARCHAR(50),
    photo_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crear tabla de información de especies
CREATE TABLE IF NOT EXISTS species_info (
    id INT AUTO_INCREMENT PRIMARY KEY,
    species_id INT NOT NULL,
    distribution TEXT,
    habitat TEXT,
    behavior TEXT,
    nesting TEXT,
    diet TEXT,
    colony_size TEXT,
    queen_info TEXT,
    worker_info TEXT,
    breeding_tips TEXT,
    interesting_facts TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE,
    UNIQUE KEY unique_species_info (species_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crear tabla de búsquedas
CREATE TABLE IF NOT EXISTS searches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query VARCHAR(255) NOT NULL,
    found_species_id INT,
    success BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (found_species_id) REFERENCES species(id) ON DELETE SET NULL,
    INDEX idx_query (query)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crear tabla de sinónimos de especies
CREATE TABLE IF NOT EXISTS species_synonyms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    species_id INT NOT NULL,
    synonym VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE,
    UNIQUE KEY unique_synonym (species_id, synonym),
    INDEX idx_synonym (synonym)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crear tabla de estadísticas de búsqueda
CREATE TABLE IF NOT EXISTS search_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    found_species_id INT NOT NULL,
    search_count INT DEFAULT 1,
    last_searched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (found_species_id) REFERENCES species(id) ON DELETE CASCADE,
    UNIQUE KEY unique_species_stats (found_species_id),
    INDEX idx_search_count (search_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Script de migración para datos existentes (solo si no se ha ejecutado antes)
DELIMITER //
DROP PROCEDURE IF EXISTS migrate_existing_data //
CREATE PROCEDURE migrate_existing_data()
BEGIN
    -- Desactivar modo seguro temporalmente
    SET SQL_SAFE_UPDATES = 0;
    
    -- Verificar si la migración ya se ha realizado
    SET @migration_done := (SELECT COUNT(*) FROM species WHERE photo_url IS NOT NULL);
    
    -- Solo ejecutar la migración si no se ha realizado antes
    IF @migration_done = 0 THEN
        -- Migrar fotos de species_images a species si existen
        IF EXISTS (SELECT 1 FROM species_images LIMIT 1) THEN
            UPDATE species s
            JOIN species_images si ON s.id = si.species_id
            SET s.photo_url = si.photo_url,
                s.inaturalist_id = si.inaturalist_id
            WHERE s.photo_url IS NULL;
        END IF;
    END IF;
    
    -- Reactivar modo seguro
    SET SQL_SAFE_UPDATES = 1;
END //
DELIMITER ;

-- Ejecutar la migración
CALL migrate_existing_data();

-- Crear función para calcular la distancia de Levenshtein (si no existe)
DELIMITER //
CREATE FUNCTION IF NOT EXISTS levenshtein_distance(s1 VARCHAR(255), s2 VARCHAR(255))
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE s1_len, s2_len, i, j, cost INT;
    DECLARE s1_char, s2_char CHAR;
    DECLARE cv0, cv1 TEXT;
    
    SET s1_len = CHAR_LENGTH(s1), s2_len = CHAR_LENGTH(s2);
    IF s1 = s2 THEN
        RETURN 0;
    ELSEIF s1_len = 0 THEN
        RETURN s2_len;
    ELSEIF s2_len = 0 THEN
        RETURN s1_len;
    END IF;
    
    SET cv1 = REPEAT('0', s2_len + 1);
    SET j = 1;
    
    WHILE j <= s2_len DO
        SET cv1 = INSERT(cv1, j, 1, j);
        SET j = j + 1;
    END WHILE;
    
    SET i = 1;
    WHILE i <= s1_len DO
        SET s1_char = SUBSTRING(s1, i, 1);
        SET cv0 = i;
        SET j = 1;
        WHILE j <= s2_len DO
            SET s2_char = SUBSTRING(s2, j, 1);
            IF s1_char = s2_char THEN SET cost = 0; ELSE SET cost = 1; END IF;
            SET cv0 = CONCAT(cv0, ',', LEAST(LEAST(
                CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(cv1, ',', j + 1), ',', -1) AS UNSIGNED) + 1,
                CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(cv0, ',', j), ',', -1) AS UNSIGNED) + 1),
                CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(cv1, ',', j), ',', -1) AS UNSIGNED) + cost));
            SET j = j + 1;
        END WHILE;
        SET cv1 = cv0;
        SET i = i + 1;
    END WHILE;
    
    RETURN CAST(SUBSTRING_INDEX(cv0, ',', -1) AS UNSIGNED);
END //
DELIMITER ;

-- Crear o reemplazar el procedimiento para buscar especies similares
DELIMITER //
DROP PROCEDURE IF EXISTS find_similar_species //
CREATE PROCEDURE find_similar_species(IN search_term VARCHAR(255))
BEGIN
    DECLARE threshold INT DEFAULT 3;
    
    -- Normalizar el término de búsqueda
    SET search_term = LOWER(TRIM(search_term));
    
    -- Buscar coincidencias en orden de prioridad
    SELECT 
        s.id,
        s.scientific_name,
        s.antwiki_url,
        s.photo_url,
        s.inaturalist_id,
        COALESCE(ss.synonym, '') as synonym,
        CASE 
            WHEN LOWER(s.scientific_name) = search_term THEN 0
            WHEN LOWER(ss.synonym) = search_term THEN 0
            ELSE levenshtein_distance(LOWER(s.scientific_name), search_term)
        END as distance,
        CASE 
            WHEN LOWER(s.scientific_name) = search_term THEN 'exact'
            WHEN LOWER(ss.synonym) = search_term THEN 'exact_synonym'
            ELSE 'similar'
        END as match_type
    FROM species s
    LEFT JOIN species_synonyms ss ON s.id = ss.species_id
    WHERE LOWER(s.scientific_name) = search_term
        OR LOWER(ss.synonym) = search_term
        OR levenshtein_distance(LOWER(s.scientific_name), search_term) <= threshold
        OR levenshtein_distance(LOWER(COALESCE(ss.synonym, '')), search_term) <= threshold
    ORDER BY 
        distance ASC,
        match_type ASC,
        scientific_name ASC
    LIMIT 1;
END //
DELIMITER ;

-- Crear o reemplazar el trigger para actualizar estadísticas
DELIMITER //
DROP TRIGGER IF EXISTS after_search_insert //
CREATE TRIGGER after_search_insert
AFTER INSERT ON searches
FOR EACH ROW
BEGIN
    IF NEW.found_species_id IS NOT NULL AND NEW.success = TRUE THEN
        INSERT INTO search_stats (found_species_id, search_count, last_searched)
        VALUES (NEW.found_species_id, 1, CURRENT_TIMESTAMP)
        ON DUPLICATE KEY UPDATE
            search_count = search_count + 1,
            last_searched = CURRENT_TIMESTAMP;
    END IF;
END //
DELIMITER ;

-- Crear o reemplazar la vista para especies más buscadas
DROP VIEW IF EXISTS most_searched_species;
CREATE VIEW most_searched_species AS
SELECT 
    s.scientific_name,
    s.antwiki_url,
    s.photo_url,
    si.distribution,
    si.habitat,
    st.search_count,
    st.last_searched
FROM species s
JOIN search_stats st ON s.id = st.found_species_id
LEFT JOIN species_info si ON s.id = si.species_id
ORDER BY st.search_count DESC, st.last_searched DESC;

-- Crear o reemplazar el trigger para agregar sinónimos automáticamente
DELIMITER //
DROP TRIGGER IF EXISTS after_species_insert //
CREATE TRIGGER after_species_insert
AFTER INSERT ON species
FOR EACH ROW
BEGIN
    -- Agregar el nombre científico como está
    INSERT IGNORE INTO species_synonyms (species_id, synonym)
    VALUES (NEW.id, NEW.scientific_name);
    
    -- Agregar variante sin espacios
    INSERT IGNORE INTO species_synonyms (species_id, synonym)
    VALUES (NEW.id, REPLACE(NEW.scientific_name, ' ', ''));
    
    -- Agregar variante con guiones bajos
    INSERT IGNORE INTO species_synonyms (species_id, synonym)
    VALUES (NEW.id, REPLACE(NEW.scientific_name, ' ', '_'));
END //
DELIMITER ; 