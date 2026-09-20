// Gradle 用哪个 JDK 由 gradlew / gradlew.bat 里的垫片决定：
// JAVA_HOME 指向 8（或未设置）时自动切换到工程自带的 .tools/jdk。
// IDEA / Android Studio 默认拿自带 Java 8 启动 Gradle，会在解析 AGP 时报
// "This build uses a Java 8 JVM" —— 那里正是这个垫片生效的地方。
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "opc-app"
include(":app")
