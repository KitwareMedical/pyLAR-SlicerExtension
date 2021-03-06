
set(proj pyLAR)

set(${proj}_DEPENDENCIES "")

ExternalProject_Include_Dependencies(${proj} PROJECT_VAR proj DEPENDS_VAR ${proj}_DEPENDENCIES)

# Sanity checks
if(DEFINED pyLAR_DIR AND NOT EXISTS ${pyLAR_DIR})
  message(FATAL_ERROR "pyLAR_DIR variable is defined but corresponds to nonexistent directory")
endif()

if(NOT ${CMAKE_PROJECT_NAME}_USE_SYSTEM_${proj})

  set(EP_SOURCE_DIR ${CMAKE_BINARY_DIR}/${proj})

  ExternalProject_add(pyLAR
    SOURCE_DIR ${EP_SOURCE_DIR}
    GIT_REPOSITORY ${git_protocol}://github.com/KitwareMedical/pyLAR.git
    GIT_TAG c57ef96a813db69597ec2a3c31972443a85846c6
    CONFIGURE_COMMAND ""
    INSTALL_COMMAND ""
    BUILD_COMMAND ""
    )
  set(pyLAR_DIR ${CMAKE_BINARY_DIR}/${proj})
else()
  ExternalProject_Add_Empty(${proj} DEPENDS ${${proj}_DEPENDENCIES})
endif()

mark_as_superbuild(
  VARS pyLAR_DIR:PATH
  LABELS "FIND_PACKAGE"
  )
