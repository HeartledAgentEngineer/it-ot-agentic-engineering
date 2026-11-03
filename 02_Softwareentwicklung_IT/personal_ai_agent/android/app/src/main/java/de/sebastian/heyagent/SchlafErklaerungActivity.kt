package de.sebastian.heyagent

import android.os.Bundle
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/**
 * Erklaerseite, die Health Connect vor der Schlaf-Erlaubnis zeigt (Pflicht laut Health Connect).
 * Reiner Text, keine Daten.
 */
class SchlafErklaerungActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val abstand = (16 * resources.displayMetrics.density).toInt()
        val text = TextView(this).apply {
            setText(R.string.schlaf_erklaerung)
            textSize = 16f
            setPadding(abstand, abstand, abstand, abstand)
        }
        setContentView(ScrollView(this).apply { addView(text) })
        setTitle(R.string.schlaf_erklaerung_titel)
    }
}
