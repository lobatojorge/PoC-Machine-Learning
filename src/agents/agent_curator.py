import os
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CuradorViz")

class VisualizationCuratorAgent:
    """
    Agente enfocado EXCLUSIVAMENTE en Visualization Observability.
    Responsabilidad única: Traducir la estadística descriptiva del dataset
    en especificaciones técnicas de frontend sin carga cognitiva.
    """
    def __init__(self, processed_dir: str, docs_dir: str):
        self.processed_dir = processed_dir
        self.docs_dir = docs_dir
        self.analyzed_files = set()
        
        logger.info("El Curador de Visualización está en línea. Esperando datos certificados.")

    def monitor_processed_zone(self):
        """Espera a que el Inspector de Datos apruebe un dataset."""
        logger.info(f"Vigilando entradas en zona procesada: {self.processed_dir}...")
        try:
            while True:
                for filename in os.listdir(self.processed_dir):
                    if filename.endswith(".csv") and filename not in self.analyzed_files:
                        self._analyze_and_recommend(filename)
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Curador apagado.")

    def _analyze_and_recommend(self, filename: str):
        filepath = os.path.join(self.processed_dir, filename)
        logger.info(f"Nuevo dataset certificado detectado: {filename}. Iniciando perfilado estadístico.")
        
        # 1. Extraer meta-características del dataset
        stats = self._statistical_profiling(filepath)
        
        # 2. Sintetizar reglas cognitivas y de accesibilidad
        recommendations = self._generate_viz_specs(filename, stats)
        
        # 3. Empaquetar recomendaciones para el desarrollador Frontend
        self._export_recommendations(recommendations)
        
        self.analyzed_files.add(filename)

    def _statistical_profiling(self, filepath: str) -> dict:
        """
        Analiza tipos de datos, correlaciones y cardinalidad.
        En producción usaría YData Profiling o Pandas.
        """
        logger.info("Calculando matriz de características para diseño de VIZ...")
        return {
            "n_categorias_zona": 7,     # Simulación: Zonas de pesca (Alta cardinalidad)
            "n_variables_continuas": 4,  # Ej: Peso, Longitud, Edad, Temperatura
            "time_series_detected": True,# Columna de fechas consecutivas validada
            "strongest_correlation": ["peso", "longitud"]
        }

    def _generate_viz_specs(self, source_file: str, stats: dict) -> dict:
        """Motor de inferencia de Diseño y Accesibilidad Cognitiva."""
        logger.info("Generando manifiesto de diseño...")
        specs = {
            "dataset_origen": source_file,
            "grafico_sugerido": [],
            "alertas_carga_cognitiva": [],
            "alertas_accesibilidad": []
        }

        # Lógica de curación algorítmica
        if stats.get("time_series_detected"):
            specs["grafico_sugerido"].append("Serie temporal (geom_line / LineChart) para evolución de capturas 2004-2020.")
            
        if "peso" in stats.get("strongest_correlation", []) and "longitud" in stats.get("strongest_correlation", []):
            specs["grafico_sugerido"].append("Scatterplot para análisis de Condición Corporal (Relación Peso-Longitud).")

        if stats.get("n_categorias_zona", 0) > 5:
            specs["alertas_carga_cognitiva"].append(
                "Múltiples zonas geográficas detectadas (>5). EVITAR un único gráfico con 7 colores. "
                "Carga cognitiva excesiva. Faceteado recomendado (Small Multiples)."
            )

        if stats.get("n_variables_continuas", 0) > 0:
            specs["alertas_accesibilidad"].append(
                "Mapeo de color a variable continua: Requerida paleta Colorblind-safe, estrictamente perceptualmente uniforme (ej. Viridis, Cividis)."
            )

        return specs

    def _export_recommendations(self, recommendations: dict):
        """Genera el JSON en la carpeta docs para que el Frontend/Dashboards lo consuma."""
        out_path = os.path.join(self.docs_dir, "recomendaciones_viz.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(recommendations, f, indent=4, ensure_ascii=False)
        logger.info(f"Recomendaciones publicadas de forma exitosa en: {out_path}")

if __name__ == "__main__":
    curador = VisualizationCuratorAgent(
        processed_dir=os.path.join("data", "processed"),
        docs_dir="docs"
    )
    # curador.monitor_processed_zone()
