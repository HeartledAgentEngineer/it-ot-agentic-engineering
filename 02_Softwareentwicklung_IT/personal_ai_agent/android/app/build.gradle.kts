plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "de.sebastian.heyagent"
    compileSdk = 35

    defaultConfig {
        // Leicht aenderbar: nur hier (und namespace oben, falls das Paket umbenannt wird).
        applicationId = "de.sebastian.heyagent"
        minSdk = 29
        targetSdk = 35
        versionCode = 3
        versionName = "0.3-alltag"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    // Verschluesselter Schluesselspeicher (Android-Keystore). MasterKey gibt es ab 1.1.0-alpha.
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    // Schlaf der Uhr aus Health Connect lesen (nur READ_SLEEP, Issue #12).
    // beta01 ist die letzte Version fuer compileSdk 35 / AGP 8.7 (ab beta02: compileSdk 36, AGP 8.9.1).
    implementation("androidx.health.connect:connect-client:1.1.0-beta01")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    // Stuendliches Alltags-Pop-up (S7). 2.9.1: letzte Fassung fuer compileSdk 34/35.
    implementation("androidx.work:work-runtime-ktx:2.9.1")

    testImplementation("junit:junit:4.13.2")
}
