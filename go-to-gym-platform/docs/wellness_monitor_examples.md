# Ejemplos de Consumo del Microservicio `wellness_monitor`

A continuación se muestran ejemplos de cómo las apps móviles pueden enviar métricas de salud al endpoint `/api/metrics/upload/` protegido con JWT.

## Google Fit (PWA / JavaScript)
```javascript
async function sendMetric(token, metric) {
  await fetch('https://your-domain.com/api/metrics/upload/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(metric)
  });
}

// Ejemplo de métrica obtenida con OAuth de Google Fit
sendMetric(jwtToken, {
  user: 1,
  source: 'GoogleFit',
  metric_type: 'steps',
  value: 1200,
  timestamp: new Date().toISOString()
});
```

## Apple Health (Swift)
```swift
let url = URL(string: "https://your-domain.com/api/metrics/upload/")!
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.addValue("Bearer \(jwtToken)", forHTTPHeaderField: "Authorization")
request.addValue("application/json", forHTTPHeaderField: "Content-Type")

let payload: [String: Any] = [
    "user": userId,
    "source": "AppleHealth",
    "metric_type": "heart_rate",
    "value": 82,
    "timestamp": ISO8601DateFormatter().string(from: Date())
]
request.httpBody = try JSONSerialization.data(withJSONObject: payload)

URLSession.shared.dataTask(with: request).resume()
```

## Samsung Health (Android Kotlin con Retrofit)
```kotlin
interface ApiService {
    @POST("api/metrics/upload/")
    suspend fun upload(@Body metric: MetricDto, @Header("Authorization") token: String)
}

val metric = MetricDto(
    user = userId,
    source = "SamsungHealth",
    metric_type = "sleep",
    value = 7.5f,
    timestamp = Instant.now().toString()
)
apiService.upload(metric, "Bearer $jwtToken")
```
