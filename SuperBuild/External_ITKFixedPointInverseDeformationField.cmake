
set(proj ITKFixedPointInverseDeformationField)

# Set dependency list
set(${proj}_DEPENDENCIES ITKv4)

# Include dependent projects if any
ExternalProject_Include_Dependencies(${proj} PROJECT_VAR proj DEPENDS_VAR ${proj}_DEPENDENCIES)

# Sanity checks
if(DEFINED ITKFixedPointInverseDeformationField_DIR AND NOT EXISTS ${ITKFixedPointInverseDeformationField_DIR})
  message(FATAL_ERROR "ANTS_DIR variable is defined but corresponds to nonexistent directory")
endif()

if(NOT ${CMAKE_PROJECT_NAME}_USE_SYSTEM_${proj})

  include(ExternalProjectForNonCMakeProject)

#-----------------------------------------------------------------------------
# Add external dependencies: pyLAR library
set(proj ITKFixedPointInverseDeformationField)
ExternalProject_Add(${proj}
  ${${proj}_EP_ARGS}
  GIT_REPOSITORY ${git_protocol}://github.com/KitwareMedical/ITKFixedPointInverseDeformationField.git
  GIT_TAG 1a975a10615c9c6fbf03ba565268ca3e3a6ee8da
  SOURCE_DIR ${proj}
  BINARY_DIR ${proj}-build
  CMAKE_GENERATOR ${gen}
  CMAKE_ARGS
    -DCMAKE_CXX_COMPILER:FILEPATH=${CMAKE_CXX_COMPILER}
    -DCMAKE_CXX_FLAGS:STRING=${ep_common_cxx_flags}
    -DCMAKE_C_COMPILER:FILEPATH=${CMAKE_C_COMPILER}
    -DCMAKE_C_FLAGS:STRING=${ep_common_c_flags}
    -DCMAKE_BUILD_TYPE:STRING=${CMAKE_BUILD_TYPE}
    -DINSTALL_RUNTIME_DESTINATION:STRING=${Slicer_INSTALL_ExternalBinMODULES_BIN_DIR}
	-DITK_DIR:PATH=${ITK_DIR}
  INSTALL_COMMAND ""
  DEPENDS
    ${${proj}_DEPENDENCIES}
)
  set(ITKFixedPointInverseDeformationField_DIR ${CMAKE_BINARY_DIR}/${proj}-build)
else()
  ExternalProject_Add_Empty(${proj} DEPENDS ${${proj}_DEPENDENCIES})
endif()

mark_as_superbuild(
  VARS ITKFixedPointInverseDeformationField_DIR:PATH
  LABELS "FIND_PACKAGE"
  )