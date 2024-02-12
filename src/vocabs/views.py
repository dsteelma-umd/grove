from typing import Any

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from plastron.namespaces import namespace_manager, rdf
from rdflib.util import from_n3

from vocabs.forms import PropertyForm
from vocabs.models import Predicate, Property, Term, Vocabulary


class PrefixList(View):
    def get(self, request, *args, **kwargs):
        prefixes = {prefix: uri for prefix, uri in namespace_manager.namespaces()}
        return render(request, 'vocabs/prefix_list.html', {'prefixes': dict(sorted(prefixes.items()))})


class IndexView(ListView):
    model = Vocabulary
    context_object_name = 'vocabularies'

    def post(self, request, *args, **kwargs):
        uri = request.POST.get('vocabulary_uri', '').strip()
        if uri != '':
            vocab, is_new = Vocabulary.objects.get_or_create(
                uri=uri
            )

        return HttpResponseRedirect(reverse('show_vocabulary', args=(vocab.id,)))


class VocabularyView(DetailView):
    model = Vocabulary
    context_object_name = 'vocabulary'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update({
            'predicates': Predicate.objects.all,
        })
        return context

    def post(self, request, pk, *args, **kwargs):
        vocabulary = self.get_object()
        name = request.POST.get('term_name', '').strip()
        rdf_type = request.POST.get('rdf_type', '').strip()
        if name != '':
            term, is_new = Term.objects.get_or_create(
                vocabulary=vocabulary,
                name=name,
            )
            if rdf_type != '':
                predicate, _ = Predicate.objects.get_or_create(uri=str(rdf.type), object_type=Predicate.ObjectType.URI_REF)
                Property.objects.get_or_create(
                    term=term,
                    predicate=predicate,
                    value=from_n3(rdf_type),
                )

        return HttpResponseRedirect(reverse('show_vocabulary', args=(pk,)))


class GraphView(DetailView):
    model = Vocabulary

    def get(self, request, pk, *args, **kwargs):
        graph, context = self.get_object().graph()
        return HttpResponse(graph.serialize(format='json-ld', context=context), headers={'Content-Type': 'application/ld+json; charset=utf-8'})


class TermView(DetailView):
    model = Term
    context_object_name = 'term'

    @method_decorator(ensure_csrf_cookie)
    def delete(self, request, pk, *args, **kwargs):
        self.get_object().delete()
        return HttpResponse()

class PropertyView(DetailView):
    model = Property
    context_object_name = 'property'

    @method_decorator(ensure_csrf_cookie)
    def delete(self, request, pk, *args, **kwargs):
        self.get_object().delete()
        return HttpResponse()


class NewPropertyView(CreateView):
    model = Property
    form_class = PropertyForm
    template_name = 'vocabs/new_property.html'

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()
        if self.request.method == 'GET':
            curie = self.request.GET['predicate']
            term = Term.objects.get(id=self.request.GET['term_id'])
            initial.update({
                'term': term,
                'predicate': Predicate.from_curie(curie)
            })
        return initial

    def get_success_url(self) -> str:
        return reverse('show_property', args=(self.object.id,))


class PropertyEditView(UpdateView):
    model = Property
    form_class = PropertyForm

    def get_initial(self):
        return {
            'term': self.object.term,
            'predicate': self.object.predicate,
            'value': self.object.value_for_editing,
        }

    def get_success_url(self) -> str:
        return reverse('show_property', args=(self.object.id,))


class PredicatesView(ListView):
    model = Predicate

    # create new Predicate
    def post(self, request, *args, **kwargs):
        uri = request.POST.get('new_predicate', '').strip()
        if uri != '':
            if not uri.startswith('http:') or uri.startswith('https:'):
                uri = from_n3(uri, nsm=namespace_manager)
            Predicate.objects.get_or_create(
                uri=uri,
                object_type=request.POST.get('object_type', '')
            )

        return HttpResponseRedirect(reverse('list_predicates'))
