plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.quishguard.webviewtest"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.quishguard.webviewtest"
        minSdk = 24
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            optimization {
                enable = true
                packageScope = setOf("androidx.**", "kotlin.**", "kotlinx.**")
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    implementation(libs.androidx.activity.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.constraintlayout)
    implementation(libs.androidx.core.ktx)
    implementation("androidx.webkit:webkit:1.11.0")   // WebViewCompat / WebViewFeature: document-start script + feature checks
    implementation(libs.material)
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
}

// Keep the Android sensor identical to the Python lab's canonical sensor (single source of truth).
val copySensorJs by tasks.registering(Copy::class) {
    from(rootProject.projectDir.parentFile.resolve("src/quishguard/sensor.js"))
    into(layout.projectDirectory.dir("src/main/assets"))
}
tasks.named("preBuild") { dependsOn(copySensorJs) }
