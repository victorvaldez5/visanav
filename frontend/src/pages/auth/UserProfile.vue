<template>
  <div class="my-6 px-6 sm:px-8 lg:px-12">
    <div class="min-w-0 flex-1">
      <h2 class="text-2xl/7 font-semibold text-foreground sm:truncate sm:text-3xl sm:tracking-tight">
        {{ t("profile.title") }}
      </h2>
    </div>
  </div>
  <div v-if="loading">
    {{ t("profile.loading") }}
  </div>
  <form
    v-else
    class="max-w-3xl mx-auto py-4"
    @submit.prevent="onSubmit"
  >
    <div class="space-y-12">
      <div
        class="grid grid-cols-1 gap-x-8 gap-y-10 pb-12 md:grid-cols-3"
      >
        <div>
          <h2 class="text-base/7 font-semibold text-foreground">
            {{ t("profile.profileHeading") }}
          </h2>
          <p class="mt-1 text-sm/6 text-muted-foreground">
            {{ t("profile.profileDesc") }}
          </p>
        </div>

        <div
          class="grid max-w-2xl grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6 md:col-span-2"
        >
          <div class="sm:col-span-4">
            <FormField
              v-slot="{ componentField }"
              v-model="values.email"
              name="email"
              validate-on-change
              :validate-on-blur="false"
            >
              <FormItem>
                <FormLabel>{{ t("profile.email") }}</FormLabel>
                <FormControl>
                  <Input
                    type="email"
                    v-bind="componentField"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>
          <div class="sm:col-span-4">
            <FormField
              v-slot="{ componentField }"
              v-model="values.phone_number"
              name="phone_number"
              validate-on-change
              :validate-on-blur="false"
            >
              <FormItem>
                <FormLabel>{{ t("profile.phone") }}</FormLabel>
                <FormControl>
                  <Input
                    type="text"
                    v-bind="componentField"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>
          <div class="sm:col-span-4">
            <FormField
              v-model="values.preferred_language"
              name="preferred_language"
              validate-on-change
              :validate-on-blur="false"
            >
              <FormItem class="flex flex-col">
                <FormLabel>{{ t("profile.preferredLanguage") }}</FormLabel>
                <Combobox
                  v-model="values.preferred_language"
                  by="label"
                  open-on-click
                >
                  <FormControl>
                    <ComboboxAnchor>
                      <div class="relative w-full max-w-sm items-center">
                        <ComboboxInput
                          :display-value="(val) => val?.name || ''"
                          :placeholder="t('profile.selectLanguage')"
                        />
                        <ComboboxTrigger
                          class="absolute end-0 inset-y-0 flex items-center justify-center px-3"
                        >
                          <ChevronsUpDown class="size-4 text-muted-foreground" />
                        </ComboboxTrigger>
                      </div>
                    </ComboboxAnchor>
                  </FormControl>

                  <ComboboxList
                    position="popper"
                  >
                    <ComboboxViewport>
                      <ComboboxEmpty>{{ t("common.noResults") }}</ComboboxEmpty>

                      <ComboboxGroup>
                        <ComboboxItem
                          v-for="language in languages"
                          :key="language.code"
                          :value="language"
                          @select="() => setFieldValue('preferred_language', language)"
                        >
                          {{ language.name }}
                        </ComboboxItem>
                      </ComboboxGroup>
                    </ComboboxViewport>
                  </ComboboxList>
                </Combobox>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>
        </div>
      </div>

      <!-- Personal Information section -->
      <div
        class="grid grid-cols-1 gap-x-8 gap-y-10 pb-12 md:grid-cols-3"
      >
        <div>
          <h2
            class="text-base/7 font-semibold text-foreground"
          >
            {{ t("profile.personalHeading") }}
          </h2>
          <p class="mt-1 text-sm/6 text-muted-foreground">
            {{ t("profile.personalDesc") }}
          </p>
        </div>

        <div
          class="grid max-w-2xl grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6 md:col-span-2"
        >
          <div class="sm:col-span-2">
            <FormField
              v-slot="{ componentField }"
              v-model="values.first_name"
              name="first_name"
              validate-on-change
              :validate-on-blur="false"
            >
              <FormItem>
                <FormLabel>{{ t("profile.firstName") }}</FormLabel>
                <FormControl>
                  <Input
                    type="text"
                    v-bind="componentField"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>

          <div class="sm:col-span-2">
            <FormField
              v-slot="{ componentField }"
              v-model="values.middle_name"
              name="middle_name"
              validate-on-change
              :validate-on-blur="false"
            >
              <FormItem>
                <FormLabel>{{ t("profile.middleName") }}</FormLabel>
                <FormControl>
                  <Input
                    type="text"
                    v-bind="componentField"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>

          <div class="sm:col-span-2">
            <FormField
              v-slot="{ componentField }"
              v-model="values.last_name"
              name="last_name"
              validate-on-change
              :validate-on-blur="false"
            >
              <FormItem>
                <FormLabel>{{ t("profile.lastName") }}</FormLabel>
                <FormControl>
                  <Input
                    type="text"
                    v-bind="componentField"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>

          <div class="sm:col-span-3">
            <FormField
              v-model="values.country"
              name="country"
              validate-on-change
              :validate-on-blur="false"
            >
              <FormItem class="flex flex-col">
                <FormLabel>{{ t("profile.country") }}</FormLabel>
                <Combobox
                  v-model="values.country"
                  by="label"
                  open-on-click
                >
                  <FormControl>
                    <ComboboxAnchor>
                      <div class="relative w-full max-w-sm items-center">
                        <ComboboxInput
                          :display-value="(val) => val?.name || ''"
                          :placeholder="t('profile.selectCountry')"
                        />
                        <ComboboxTrigger
                          class="absolute end-0 inset-y-0 flex items-center justify-center px-3"
                        >
                          <ChevronsUpDown class="size-4 text-muted-foreground" />
                        </ComboboxTrigger>
                      </div>
                    </ComboboxAnchor>
                  </FormControl>

                  <ComboboxList
                    position="popper"
                  >
                    <ComboboxViewport>
                      <ComboboxEmpty>{{ t("common.noResults") }}</ComboboxEmpty>

                      <ComboboxGroup class="overflow-y-scroll">
                        <ComboboxItem
                          v-for="country in countries"
                          :key="country.country_code"
                          :value="country"
                          @select="handleCountrySelect(country)"
                        >
                          {{ country.name }}
                        </ComboboxItem>
                      </ComboboxGroup>
                    </ComboboxViewport>
                  </ComboboxList>
                </Combobox>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>
          <div class="sm:col-span-3">
            <FormField
              v-model="values.subdivision"
              name="subdivision"
              validate-on-change
              :validate-on-blur="false"
            >
              <FormItem class="flex flex-col">
                <FormLabel>{{ t("profile.subdivision") }}</FormLabel>
                <Combobox
                  v-model="values.subdivision"
                  by="label"
                  :disabled="values.country === null"
                  open-on-click
                >
                  <FormControl>
                    <ComboboxAnchor>
                      <div class="relative w-full max-w-sm items-center">
                        <ComboboxInput
                          :display-value="(val) => val?.name || ''"
                          :placeholder="t('profile.selectSubdivision')"
                        />
                        <ComboboxTrigger
                          class="absolute end-0 inset-y-0 flex items-center justify-center px-3"
                        >
                          <ChevronsUpDown class="size-4 text-muted-foreground" />
                        </ComboboxTrigger>
                      </div>
                    </ComboboxAnchor>
                  </FormControl>

                  <ComboboxList
                    position="popper"
                  >
                    <ComboboxViewport>
                      <ComboboxEmpty>{{ t("common.noResults") }}</ComboboxEmpty>

                      <ComboboxGroup class="overflow-y-scroll">
                        <ComboboxItem
                          v-for="subdivision in subdivisions"
                          :key="subdivision.id"
                          :value="subdivision"
                          @select="() => setFieldValue('subdivision', subdivision)"
                        >
                          {{ subdivision.name }}
                        </ComboboxItem>
                      </ComboboxGroup>
                    </ComboboxViewport>
                  </ComboboxList>
                </Combobox>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>


          <div class="sm:col-span-2">
            <FormField
              v-slot="{ componentField }"
              v-model="values.postal_code"
              name="postal_code"
              validate-on-change
              :validate-on-blur="false"
            >
              <FormItem>
                <FormLabel>{{ t("profile.postalCode") }}</FormLabel>
                <FormControl>
                  <Input
                    type="text"
                    v-bind="componentField"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>
        </div>
      </div>

      <div
        class="grid grid-cols-1 gap-x-8 gap-y-10 pb-12 md:grid-cols-3"
      >
        <div>
          <h2
            class="text-base/7 font-semibold text-foreground"
          >
            {{ t("profile.notificationsHeading") }}
          </h2>
          <p class="mt-1 text-sm/6 text-muted-foreground">
            {{ t("profile.notificationsDesc") }}
          </p>
        </div>

        <div class="max-w-2xl space-y-10 md:col-span-2">
          <FormField
            v-slot="{ value, handleChange }"
            name="notify_system"
            validate-on-change
            :validate-on-blur="false"
          >
            <FormItem>
              <FormControl>
                <Switch
                  :model-value="value"
                  @update:model-value="handleChange"
                />
              </FormControl>
              <FormLabel>{{ t("profile.notifySystem") }}</FormLabel>
            </FormItem>
          </FormField>
          <FormField
            v-slot="{ value, handleChange }"
            name="notify_marketing"
            validate-on-change
            :validate-on-blur="false"
          >
            <FormItem>
              <FormControl>
                <Switch
                  :model-value="value"
                  @update:model-value="handleChange"
                />
              </FormControl>
              <FormLabel>{{ t("profile.notifyMarketing") }}</FormLabel>
            </FormItem>
          </FormField>
        </div>
      </div>
    </div>

    <div class="mt-6 flex items-center justify-end gap-x-6">
      <Button
        type="button"
        variant="ghost"
      >
        {{ t("common.cancel") }}
      </Button>
      <Button
        type="submit"
      >
        {{ t("common.save") }}
      </Button>
    </div>
  </form>
</template>

<script setup lang="ts">
import {useForm} from 'vee-validate';
import {toTypedSchema} from "@vee-validate/zod";
import {ChevronsUpDown} from "@lucide/vue";
import * as z from "zod";
import {Input} from "@/components/ui/input/index.js";
import {Switch} from "@/components/ui/switch";
import {FormControl, FormField, FormItem, FormLabel, FormMessage} from "@/components/ui/form";
import {useRoute} from "vue-router";
import {useI18n} from "vue-i18n";
import {computed, onMounted} from "vue";
import {useProfileStore} from "@/stores/useProfileStore.ts";
import {storeToRefs} from "pinia";
import {toast} from "vue-sonner";
import {currentLocale, isLocale, setLocale} from "@/i18n";
import {
  Combobox,
  ComboboxAnchor,
  ComboboxEmpty,
  ComboboxGroup,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
  ComboboxViewport,
} from "@/components/ui/combobox";
import {Button} from "@/components/ui/button";

interface ProfileForm {
  email: string
  phone_number: string | null
  first_name: string | null
  middle_name: string | null
  last_name: string | null
  country: any | null
  subdivision: any | null
  postal_code: string | null
  preferred_language: any | null
  notify_marketing: boolean | null
  notify_system: boolean | null
}

const {t} = useI18n();
const route = useRoute();
const profileStore = useProfileStore();
const {user, profile, loading, countries, subdivisions, languages} = storeToRefs(profileStore);

const userId = computed<number | null>(() => {
  const param = route.params.userId;
  return param ? Number(param) : null;
});

const formSchema = toTypedSchema(z.object({
  email: z.string().min(1, t("profile.emailRequired")).email(t("profile.emailInvalid")),
  phone_number: z.string().nullable().optional(),
  first_name: z.string().nullable().optional(),
  middle_name: z.string().nullable().optional(),
  last_name: z.string().nullable().optional(),
  country: z.any().nullable().optional(),
  subdivision: z.any().nullable().optional(),
  preferred_language: z.any().nullable().optional(),
  postal_code: z.string().nullable().optional(),
  notify_marketing: z.boolean().optional(),
  notify_system: z.boolean().optional(),
}));

const {values, setValues, handleSubmit, setFieldValue} = useForm<ProfileForm>({
  validationSchema: formSchema,
});


onMounted(async () => {
  await profileStore.loadByUserId(userId.value);
  let _country = null;
  let _subdivision = null;
  let _language = null;

  if (profile.value?.country !== null) {
    _country = profileStore.getCountryById(profile.value?.country)
    await profileStore.loadSubdivisions(_country?.country_code)

    if (profile.value?.subdivision !== null) {
      _subdivision = profileStore.getSubdivisionById(profile.value?.subdivision)
    }
  }
  if (profile.value?.preferred_language !== null) {
    _language = profileStore.getLanguageById(profile.value?.preferred_language)
  }
  setValues({
    email: user.value.email,
    first_name: user.value.first_name,
    middle_name: user.value.middle_name,
    last_name: user.value.last_name,
    phone_number: user.value.phone_number,

    // Profile
    country: _country,
    subdivision: _subdivision,
    preferred_language: _language,
    postal_code: profile.value?.postal_code,
    notify_marketing: profile.value?.notify_marketing,
    notify_system: profile.value?.notify_system
  }, false)
})

const onSubmit = handleSubmit(async (_values) => {
  try {
    const resp = await profileStore.updateProfile(userId.value!, _values)

    let _country = null;
    let _subdivision = null;
    let _language = null;

    if (resp.country !== null) {
      _country = profileStore.getCountryById(resp.country)
      await profileStore.loadSubdivisions(_country?.country_code)

      if (resp.subdivision !== null) {
        _subdivision = profileStore.getSubdivisionById(resp.subdivision)
      }
    }
    if (resp.preferred_language !== null) {
      _language = profileStore.getLanguageById(resp.preferred_language)
    }
    // Saving a preferred language is a language choice: apply it to the UI too.
    if (isLocale(resp.preferred_language) && resp.preferred_language !== currentLocale()) {
      await setLocale(resp.preferred_language)
    }
    setValues({
      email: resp.email,
      first_name: resp.first_name,
      middle_name: resp.middle_name,
      last_name: resp.last_name,
      phone_number: resp.phone_number,

      country: _country,
      subdivision: _subdivision,
      preferred_language: _language,
      postal_code: resp.postal_code,
      notify_marketing: resp.notify_marketing,
      notify_system: resp.notify_system

    })
    toast.success(t("profile.updated"))
  } catch (e) {
    console.error(e)
    toast.error(t("common.genericError"))
  }
}, (errors) => {
  console.error(errors)
})

async function handleCountrySelect(country: any, clearSubdivision = true) {
  setFieldValue('country', country)
  if (clearSubdivision) {
    setFieldValue("subdivision", null)
  }
  try {
    await profileStore.loadSubdivisions(country.country_code)
  } catch (e) {
    console.error(e)
    toast.error(t("profile.subdivisionsError"))
  }
}
</script>
