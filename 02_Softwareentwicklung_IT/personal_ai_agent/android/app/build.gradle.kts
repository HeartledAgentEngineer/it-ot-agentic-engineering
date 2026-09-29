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
        versionCode = 1
        versionName = "0.1-a1b"
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

    testImplementation("junit:junit:4.13.2")
}
